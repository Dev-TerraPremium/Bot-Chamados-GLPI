from __future__ import annotations

import logging

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
        self.renderer = renderer or TicketNotificationMessageRenderer()
        self.metrics = metrics or NotificationMetricsRecorder(redis_client)

    def run_once(self) -> dict[str, int]:
        summary = {
            "watched": 0,
            "captured": 0,
            "sent": 0,
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
        except GLPIClientError:
            self.metrics.increment("glpi_read_failures")
            summary["failed"] += 1
            logger.warning(
                "ticket_notification_glpi_read_failed",
                extra={"ticket_id": watched_ticket.ticket_id},
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
            if not watched_ticket.requester_phone:
                summary["ignored"] += 1
                self.metrics.increment("events_ignored_without_phone")
                continue

            message = self.renderer.render_user_message(watched_ticket, event)
            result = self.dispatcher.send_message(watched_ticket.requester_phone, message)
            if result.ok:
                summary["sent"] += 1
                self.metrics.increment("events_sent")
                logger.info(
                    "ticket_notification_event_sent",
                    extra={"ticket_id": event.ticket_id, "event_type": event.event_type},
                )
            else:
                summary["failed"] += 1
                self.metrics.increment("whatsapp_send_failures")

        status = str(snapshot.ticket.get("status") or "")
        if status == "6":
            self.store.stop_watching(watched_ticket.ticket_id)
            self.metrics.increment("tickets_stopped_closed")
