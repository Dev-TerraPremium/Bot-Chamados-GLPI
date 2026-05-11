from __future__ import annotations

import logging

from app.ticket_notifications.event_mapper import TicketEventMapper
from app.ticket_notifications.event_store import TicketNotificationStore
from app.ticket_notifications.models import TicketActivitySnapshot, TicketEvent

logger = logging.getLogger(__name__)


class TicketEventDetector:
    def __init__(
        self,
        store: TicketNotificationStore,
        mapper: TicketEventMapper | None = None,
    ) -> None:
        self.store = store
        self.mapper = mapper or TicketEventMapper()

    def detect_new_events(self, snapshot: TicketActivitySnapshot) -> list[TicketEvent]:
        previous_snapshot = self.store.get_snapshot(snapshot.ticket_id)
        comparable = self.mapper.comparable_snapshot(snapshot)
        events = self.mapper.events_from_snapshot(snapshot, previous_snapshot)

        if previous_snapshot is None:
            self.store.mark_events_baseline(events)
            self.store.save_snapshot(snapshot.ticket_id, comparable)
            logger.info(
                "ticket_notification_baseline_created",
                extra={"ticket_id": snapshot.ticket_id, "events": len(events)},
            )
            return []

        new_events = [event for event in events if self.store.mark_event_seen(event)]
        self.store.save_snapshot(snapshot.ticket_id, comparable)
        return new_events
