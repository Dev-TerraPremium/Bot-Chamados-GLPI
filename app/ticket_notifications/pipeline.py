from __future__ import annotations

import logging
import time

from redis import Redis

from app.application_config.settings import AppSettings
from app.glpi_integration_reserved.glpi_future_real_client import GLPIClientError
from app.ticket_notifications.event_detector import TicketEventDetector
from app.ticket_notifications.event_reader import GLPITicketEventReader
from app.ticket_notifications.event_store import TicketNotificationStore
from app.ticket_notifications.message_renderer import TicketNotificationMessageRenderer
from app.ticket_notifications.metrics_recorder import NotificationMetricsRecorder
from app.ticket_notifications.whatsapp_dispatcher import WhatsAppNotificationDispatcher

logger = logging.getLogger(__name__)


class TicketNotificationPipeline:
    def __init__(
        self,
        *,
        settings: AppSettings,
        redis_client: Redis,
        event_reader: GLPITicketEventReader,
        dispatcher: WhatsAppNotificationDispatcher,
        store: TicketNotificationStore | None = None,
        detector: TicketEventDetector | None = None,
        renderer: TicketNotificationMessageRenderer | None = None,
        metrics: NotificationMetricsRecorder | None = None,
        backfill_service=None,
    ) -> None:
        self.settings = settings
        self.store = store or TicketNotificationStore(
            redis_client,
            watch_ttl_days=settings.ticket_notification_watch_ttl_days,
        )
        self.detector = detector or TicketEventDetector(self.store)
        self.event_reader = event_reader
        self.dispatcher = dispatcher
        self.renderer = renderer or TicketNotificationMessageRenderer(
            ticket_url_template=settings.glpi_ticket_public_url_template
        )
        self.metrics = metrics or NotificationMetricsRecorder(redis_client)
        self.backfill_service = backfill_service

    def run_once(self) -> dict[str, int]:
        summary = {
            "watched_total": 0,
            "watched": 0,
            "captured": 0,
            "sent": 0,
            "sent_internal": 0,
            "ignored": 0,
            "failed": 0,
            "stopped": 0,
            "rescheduled": 0,
            "backfilled": 0,
            "backfill_failed": 0,
        }
        lock = self.store.acquire_poll_lock()
        if not lock.acquire(blocking=True):
            self.metrics.increment("poll_lock_skipped")
            return summary
        try:
            with self.metrics.measure("poll_cycle_duration_ms"):
                summary["watched_total"] = self.store.count_watched_tickets()
                self.metrics.gauge("watched_total", summary["watched_total"])
                if self.backfill_service is not None:
                    backfill_summary = self.backfill_service.run_if_due()
                    summary["backfilled"] = backfill_summary.get("tickets_added", 0)
                    summary["backfill_failed"] = backfill_summary.get("failed", 0)
                watched_tickets = self.store.list_watched_tickets(
                    self.settings.ticket_notification_batch_size
                )
                summary["watched"] = len(watched_tickets)
                self.metrics.increment("poll_due_tickets", len(watched_tickets))
                for watched_ticket in watched_tickets:
                    try:
                        should_continue = self._process_ticket(watched_ticket, summary)
                    except Exception:
                        logger.exception(
                            "ticket_notification_ticket_process_failed",
                            extra={"ticket_id": watched_ticket.ticket_id},
                        )
                        summary["failed"] += 1
                        self.metrics.increment("ticket_process_failures")
                        should_continue = True
                    if should_continue:
                        self._reschedule_ticket(watched_ticket.ticket_id, summary)
        finally:
            try:
                lock.release()
            except Exception:
                logger.exception("ticket_notification_lock_release_failed")
                self.store.force_release_poll_lock()
        return summary

    def _process_ticket(self, watched_ticket, summary: dict[str, int]) -> bool:
        try:
            ticket = self._read_ticket(watched_ticket.ticket_id)
            if ticket and self._is_terminal_ticket(ticket) and not self._should_read_terminal_snapshot(
                watched_ticket.ticket_id,
                ticket,
            ):
                self._stop_watching_terminal(watched_ticket.ticket_id, ticket, summary)
                return False
            snapshot = self._read_snapshot(watched_ticket.ticket_id, ticket=ticket)
        except GLPIClientError as exc:
            self.metrics.increment("glpi_read_failures")
            summary["failed"] += 1
            logger.warning(
                "ticket_notification_glpi_read_failed",
                extra={"ticket_id": watched_ticket.ticket_id, "error": str(exc)},
            )
            self._send_error_alert(
                reason="falha ao consultar o GLPI",
                ticket_id=watched_ticket.ticket_id,
                detail=str(exc),
            )
            self._reschedule_ticket(
                watched_ticket.ticket_id,
                summary,
                delay_seconds=self.settings.ticket_notification_retry_delay_seconds,
            )
            return False

        events = self.detector.detect_new_events(snapshot)
        summary["captured"] += len(events)
        self.metrics.increment("events_captured", len(events))
        if events:
            logger.info(
                "ticket_notification_events_detected",
                extra={
                    "ticket_id": watched_ticket.ticket_id,
                    "events": len(events),
                    "event_types": ",".join(event.event_type for event in events),
                },
            )

        for event in events:
            if event.is_private and not self.settings.ticket_notification_include_private_events:
                summary["ignored"] += 1
                self.metrics.increment("events_ignored_private")
                logger.info(
                    "ticket_notification_event_ignored_private",
                    extra={"ticket_id": event.ticket_id, "event_type": event.event_type},
                )
                continue
            internal_numbers = self._internal_update_numbers()
            if not watched_ticket.requester_phone and not internal_numbers:
                summary["ignored"] += 1
                self.metrics.increment("events_ignored_without_phone")
                continue

            self._send_event_notifications(
                watched_ticket=watched_ticket,
                event=event,
                internal_numbers=internal_numbers,
                summary=summary,
            )

        status = str(snapshot.ticket.get("status") or "")
        if self._is_terminal_status(status):
            self._stop_watching_terminal(watched_ticket.ticket_id, snapshot.ticket, summary)
            return False
        return True

    def _read_ticket(self, ticket_id: int) -> dict | None:
        read_ticket = getattr(self.event_reader, "read_ticket", None)
        if callable(read_ticket):
            return read_ticket(ticket_id)
        return None

    def _read_snapshot(self, ticket_id: int, *, ticket: dict | None):
        try:
            return self.event_reader.read_snapshot(ticket_id, ticket=ticket)
        except TypeError:
            return self.event_reader.read_snapshot(ticket_id)

    def _should_read_terminal_snapshot(self, ticket_id: int, ticket: dict) -> bool:
        previous_snapshot = self.store.get_snapshot(ticket_id)
        if not previous_snapshot:
            return False
        previous_status = str((previous_snapshot.get("ticket") or {}).get("status") or "")
        current_status = str(ticket.get("status") or "")
        return bool(previous_status and previous_status != current_status)

    def _stop_watching_terminal(
        self,
        ticket_id: int,
        ticket: dict,
        summary: dict[str, int],
    ) -> None:
        status = str(ticket.get("status") or "")
        self.store.stop_watching(ticket_id)
        summary["stopped"] += 1
        self.metrics.increment("tickets_stopped_terminal")
        logger.info(
            "ticket_notification_watch_stopped_terminal",
            extra={"ticket_id": ticket_id, "status": status},
        )

    def _reschedule_ticket(
        self,
        ticket_id: int,
        summary: dict[str, int],
        *,
        delay_seconds: int | None = None,
    ) -> None:
        delay = max(
            0,
            self.settings.ticket_notification_poll_interval_seconds
            if delay_seconds is None
            else delay_seconds,
        )
        delay += self._stable_jitter_seconds(ticket_id, delay)
        self.store.reschedule_ticket(ticket_id, delay_seconds=delay)
        summary["rescheduled"] += 1
        self.metrics.increment("tickets_rescheduled")

    def _is_terminal_ticket(self, ticket: dict | None) -> bool:
        return self._is_terminal_status(str((ticket or {}).get("status") or ""))

    def _is_terminal_status(self, status: str) -> bool:
        terminal = {
            item.strip()
            for item in self.settings.ticket_notification_terminal_statuses.split(",")
            if item.strip()
        }
        return status in terminal

    @staticmethod
    def _stable_jitter_seconds(ticket_id: int, base_delay_seconds: int) -> int:
        if base_delay_seconds <= 1:
            return 0
        return int(ticket_id) % min(base_delay_seconds, 17)

    def _send_event_notifications(
        self,
        *,
        watched_ticket,
        event,
        internal_numbers: list[str],
        summary: dict[str, int],
    ) -> None:
        sent_keys: set[str] = set()
        if watched_ticket.requester_phone:
            user_message = self.renderer.render_user_message(watched_ticket, event)
            if self._send_to_recipient(
                phone=watched_ticket.requester_phone,
                message=user_message,
                metric_success="events_sent",
                metric_failure="whatsapp_send_failures",
                summary_key="sent",
                summary=summary,
                ticket_id=event.ticket_id,
                event_type=event.event_type,
                source_id=event.source_id,
            ):
                sent_keys.add(self._recipient_key(watched_ticket.requester_phone))

        internal_message = self.renderer.render_internal_event_message(watched_ticket, event)
        for phone in internal_numbers:
            recipient_key = self._recipient_key(phone)
            if recipient_key in sent_keys:
                self.metrics.increment("internal_events_deduplicated")
                continue
            if self._send_to_recipient(
                phone=phone,
                message=internal_message,
                metric_success="internal_events_sent",
                metric_failure="internal_events_failed",
                summary_key="sent_internal",
                summary=summary,
                ticket_id=event.ticket_id,
                event_type=event.event_type,
                source_id=event.source_id,
            ):
                sent_keys.add(recipient_key)

    def _send_to_recipient(
        self,
        *,
        phone: str,
        message: str,
        metric_success: str,
        metric_failure: str,
        summary_key: str,
        summary: dict[str, int],
        ticket_id: int | None = None,
        event_type: str = "",
        source_id: str = "",
    ) -> bool:
        result = self.dispatcher.send_message(phone, message)
        if result.ok:
            summary[summary_key] += 1
            self.metrics.increment(metric_success)
            logger.info(
                "ticket_notification_event_sent",
                extra={
                    "phone": phone,
                    "ticket_id": ticket_id,
                    "event_type": event_type,
                    "source_id": source_id,
                },
            )
            return True

        summary["failed"] += 1
        self.metrics.increment(metric_failure)
        logger.warning(
            "ticket_notification_event_send_failed",
            extra={
                "phone": phone,
                "ticket_id": ticket_id,
                "event_type": event_type,
                "source_id": source_id,
                "error": result.error,
                "status_code": result.status_code,
            },
        )
        self._send_error_alert(
            reason="falha ao enviar WhatsApp",
            detail=result.error or f"HTTP {result.status_code}",
        )
        return False

    def _send_error_alert(
        self,
        *,
        reason: str,
        ticket_id: int | None = None,
        detail: str = "",
    ) -> None:
        numbers = self._split_numbers(self.settings.ticket_notification_error_alert_numbers)
        if not numbers or not self._can_send_error_alert(reason, ticket_id):
            return

        message = self.renderer.render_error_alert_message(
            reason=reason,
            ticket_id=ticket_id,
            detail=detail[:500],
        )
        for phone in numbers:
            result = self.dispatcher.send_message(phone, message)
            if result.ok:
                self.metrics.increment("error_alerts_sent")
            else:
                self.metrics.increment("error_alerts_failed")

    def _can_send_error_alert(self, reason: str, ticket_id: int | None) -> bool:
        cooldown = max(0, self.settings.ticket_notification_error_alert_cooldown_seconds)
        if cooldown == 0:
            return True

        digest_key = self._recipient_key(f"{reason}:{ticket_id or 'global'}")
        key = f"ticket_notifications:error_alert:{digest_key}"
        return bool(self.store.redis_client.set(key, str(int(time.time())), nx=True, ex=cooldown))

    def _internal_update_numbers(self) -> list[str]:
        return self._split_numbers(self.settings.ticket_notification_internal_update_numbers)

    @staticmethod
    def _split_numbers(value: str) -> list[str]:
        return [item.strip() for item in value.split(",") if item.strip()]

    @staticmethod
    def _recipient_key(phone: str) -> str:
        digits = "".join(char for char in str(phone) if char.isdigit())
        if digits.startswith("55") and len(digits) > 10:
            digits = digits[2:]
        return digits
