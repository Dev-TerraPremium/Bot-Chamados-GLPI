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

    def run_once(self) -> dict[str, int]:
        summary = {
            "watched": 0,
            "captured": 0,
            "sent": 0,
            "sent_internal": 0,
            "ignored": 0,
            "failed": 0,
        }
        lock = self.store.acquire_poll_lock()
        if not lock.acquire(blocking=True):
            self.metrics.increment("poll_lock_skipped")
            return summary
        try:
            with self.metrics.measure("poll_cycle_duration_ms"):
                watched_tickets = self.store.list_watched_tickets(
                    self.settings.ticket_notification_batch_size
                )
                summary["watched"] = len(watched_tickets)
                for watched_ticket in watched_tickets:
                    self._process_ticket(watched_ticket, summary)
        finally:
            try:
                lock.release()
            except Exception:
                logger.exception("ticket_notification_lock_release_failed")
                self.store.force_release_poll_lock()
        return summary

    def _process_ticket(self, watched_ticket, summary: dict[str, int]) -> None:
        try:
            snapshot = self.event_reader.read_snapshot(watched_ticket.ticket_id)
        except GLPIClientError as exc:
            self.metrics.increment("glpi_read_failures")
            summary["failed"] += 1
            logger.warning(
                "ticket_notification_glpi_read_failed",
                extra={"ticket_id": watched_ticket.ticket_id},
            )
            self._send_error_alert(
                reason="falha ao consultar o GLPI",
                ticket_id=watched_ticket.ticket_id,
                detail=str(exc),
            )
            return

        events = self.detector.detect_new_events(snapshot)
        summary["captured"] += len(events)
        self.metrics.increment("events_captured", len(events))

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
        if status == "6":
            self.store.stop_watching(watched_ticket.ticket_id)
            self.metrics.increment("tickets_stopped_closed")

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
    ) -> bool:
        result = self.dispatcher.send_message(phone, message)
        if result.ok:
            summary[summary_key] += 1
            self.metrics.increment(metric_success)
            logger.info("ticket_notification_event_sent", extra={"phone": phone})
            return True

        summary["failed"] += 1
        self.metrics.increment(metric_failure)
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
