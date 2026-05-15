from __future__ import annotations

import json
import logging
import time

from redis import Redis

from app.application_config.settings import AppSettings
from app.ticket_domain.ticket_enums import TicketStatus
from app.ticket_notifications.event_detector import TicketEventDetector
from app.ticket_notifications.event_reader import GLPITicketEventReader
from app.ticket_notifications.event_store import TicketNotificationStore
from app.ticket_notifications.metrics_recorder import NotificationMetricsRecorder
from app.ticket_notifications.models import WatchedTicket

logger = logging.getLogger(__name__)


class TicketNotificationBackfillService:
    LAST_RUN_KEY = "ticket_notifications:backfill:last_run"
    LOCK_KEY = "ticket_notifications:backfill:lock"
    CHANNEL_LINK_PATTERN = "channel_link:whatsapp:*"

    def __init__(
        self,
        *,
        settings: AppSettings,
        redis_client: Redis,
        glpi_client,
        store: TicketNotificationStore,
        event_reader: GLPITicketEventReader,
        detector: TicketEventDetector,
        metrics: NotificationMetricsRecorder,
    ) -> None:
        self.settings = settings
        self.redis_client = redis_client
        self.glpi_client = glpi_client
        self.store = store
        self.event_reader = event_reader
        self.detector = detector
        self.metrics = metrics

    def run_if_due(self) -> dict[str, int]:
        summary = {"users": 0, "tickets_seen": 0, "tickets_added": 0, "failed": 0}
        if not self.settings.ticket_notification_backfill_enabled:
            return summary

        lock = self.redis_client.lock(self.LOCK_KEY, timeout=120, blocking_timeout=1)
        if not lock.acquire(blocking=True):
            self.metrics.increment("backfill_lock_skipped")
            return summary
        try:
            if not self._claim_due_window():
                return summary
            for link in self._active_channel_links():
                if summary["users"] >= self.settings.ticket_notification_backfill_user_limit:
                    break
                summary["users"] += 1
                self._backfill_user(link, summary)
        finally:
            try:
                lock.release()
            except Exception:
                logger.exception("ticket_notification_backfill_lock_release_failed")
                self.redis_client.delete(self.LOCK_KEY)

        self.metrics.increment("backfill_users_scanned", summary["users"])
        self.metrics.increment("backfill_tickets_seen", summary["tickets_seen"])
        self.metrics.increment("backfill_tickets_added", summary["tickets_added"])
        if summary["failed"]:
            self.metrics.increment("backfill_failures", summary["failed"])
        logger.info("ticket_notification_backfill_completed", extra=summary)
        return summary

    def _claim_due_window(self) -> bool:
        interval = max(60, self.settings.ticket_notification_backfill_interval_seconds)
        now = int(time.time())
        last_run = int(self.redis_client.get(self.LAST_RUN_KEY) or 0)
        if last_run and now - last_run < interval:
            return False
        self.redis_client.set(self.LAST_RUN_KEY, str(now), ex=interval * 2)
        return True

    def _active_channel_links(self):
        for key in self.redis_client.scan_iter(self.CHANNEL_LINK_PATTERN, count=100):
            raw_value = self.redis_client.get(key)
            if not raw_value:
                continue
            try:
                link = json.loads(raw_value)
            except json.JSONDecodeError:
                continue
            if str(link.get("status") or "").casefold() != "active":
                continue
            user_id = int(link.get("glpi_user_id") or 0)
            phone = str(link.get("channel_identifier") or "").strip()
            if not user_id or not phone:
                continue
            yield {
                "user_id": user_id,
                "phone": phone,
                "display_name": str(link.get("display_name") or ""),
                "login": str(link.get("glpi_login") or user_id),
            }

    def _backfill_user(self, link: dict, summary: dict[str, int]) -> None:
        try:
            tickets = self.glpi_client.get_my_tickets(link["user_id"])
        except Exception:
            summary["failed"] += 1
            logger.exception(
                "ticket_notification_backfill_user_failed",
                extra={"glpi_user_id": link["user_id"]},
            )
            return

        for ticket in tickets[: self.settings.ticket_notification_backfill_tickets_per_user]:
            summary["tickets_seen"] += 1
            if ticket.status == TicketStatus.CLOSED.value:
                if self.store.is_watching(ticket.ticket_number):
                    self.store.stop_watching(ticket.ticket_number)
                continue
            if self.store.is_watching(ticket.ticket_number):
                continue
            self._watch_existing_ticket(ticket, link, summary)

    def _watch_existing_ticket(self, ticket, link: dict, summary: dict[str, int]) -> None:
        watched_ticket = WatchedTicket(
            ticket_id=ticket.ticket_number,
            requester_phone=link["phone"],
            requester_name=link["display_name"],
            requester_login=link["login"],
            category_name=ticket.category_name,
            title=ticket.title,
            location=ticket.location,
            created_at=ticket.created_at,
            channel="whatsapp",
        )
        try:
            self.store.watch_ticket(
                watched_ticket,
                next_poll_at=time.time() + self.settings.ticket_notification_poll_interval_seconds,
            )
            snapshot = self.event_reader.read_snapshot(ticket.ticket_number)
            self.detector.detect_new_events(snapshot)
        except Exception:
            self.store.stop_watching(ticket.ticket_number)
            summary["failed"] += 1
            logger.exception(
                "ticket_notification_backfill_ticket_failed",
                extra={"ticket_id": ticket.ticket_number},
            )
            return

        summary["tickets_added"] += 1
        logger.info(
            "ticket_notification_backfill_watch_registered",
            extra={"ticket_id": ticket.ticket_number, "glpi_user_id": link["user_id"]},
        )
