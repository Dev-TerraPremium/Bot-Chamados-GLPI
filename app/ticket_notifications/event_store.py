from __future__ import annotations

import hashlib
import json
import logging
import time
from typing import Iterable

from redis import Redis

from app.ticket_notifications.models import TicketEvent, WatchedTicket

logger = logging.getLogger(__name__)


class TicketNotificationStore:
    WATCHED_SET = "ticket_notifications:watched"
    LOCK_KEY = "ticket_notifications:poll_lock"

    def __init__(
        self,
        redis_client: Redis,
        *,
        watch_ttl_days: int = 30,
        recent_events_ttl_seconds: int = 172800,
    ) -> None:
        self.redis_client = redis_client
        self.watch_ttl_seconds = max(1, watch_ttl_days) * 86400
        self.recent_events_ttl_seconds = recent_events_ttl_seconds

    def watch_ticket(
        self,
        watched_ticket: WatchedTicket,
        *,
        next_poll_at: float | None = None,
    ) -> None:
        payload = json.dumps(watched_ticket.to_dict(), ensure_ascii=False)
        key = self._ticket_key(watched_ticket.ticket_id)
        score = time.time() if next_poll_at is None else next_poll_at
        pipe = self.redis_client.pipeline()
        pipe.setex(key, self.watch_ttl_seconds, payload)
        pipe.zadd(self.WATCHED_SET, {str(watched_ticket.ticket_id): score})
        pipe.execute()

    def is_watching(self, ticket_id: int) -> bool:
        return bool(self.redis_client.exists(self._ticket_key(ticket_id)))

    def count_watched_tickets(self) -> int:
        return int(self.redis_client.zcard(self.WATCHED_SET) or 0)

    def list_watched_tickets(
        self,
        limit: int,
        *,
        now: float | None = None,
    ) -> list[WatchedTicket]:
        current_time = time.time() if now is None else now
        ticket_ids = self.redis_client.zrangebyscore(
            self.WATCHED_SET,
            min="-inf",
            max=current_time,
            start=0,
            num=max(0, limit),
        )
        watched: list[WatchedTicket] = []
        stale_ids: list[str] = []
        for ticket_id in ticket_ids:
            raw_value = self.redis_client.get(self._ticket_key(int(ticket_id)))
            if not raw_value:
                stale_ids.append(str(ticket_id))
                continue
            try:
                watched.append(WatchedTicket.from_dict(json.loads(raw_value)))
            except Exception:
                logger.exception(
                    "ticket_notification_watched_ticket_decode_failed",
                    extra={"ticket_id": ticket_id},
                )
                stale_ids.append(str(ticket_id))
        if stale_ids:
            self.redis_client.zrem(self.WATCHED_SET, *stale_ids)
        return watched

    def reschedule_ticket(
        self,
        ticket_id: int,
        *,
        delay_seconds: int,
        now: float | None = None,
    ) -> None:
        current_time = time.time() if now is None else now
        self.redis_client.zadd(
            self.WATCHED_SET,
            {str(ticket_id): current_time + max(0, delay_seconds)},
        )

    def stop_watching(self, ticket_id: int) -> None:
        pipe = self.redis_client.pipeline()
        pipe.delete(self._ticket_key(ticket_id))
        pipe.delete(self._snapshot_key(ticket_id))
        pipe.zrem(self.WATCHED_SET, str(ticket_id))
        pipe.execute()

    def get_snapshot(self, ticket_id: int) -> dict | None:
        raw_value = self.redis_client.get(self._snapshot_key(ticket_id))
        if not raw_value:
            return None
        try:
            return json.loads(raw_value)
        except Exception:
            logger.exception(
                "ticket_notification_snapshot_decode_failed",
                extra={"ticket_id": ticket_id},
            )
            return None

    def save_snapshot(self, ticket_id: int, snapshot: dict) -> None:
        self.redis_client.setex(
            self._snapshot_key(ticket_id),
            self.watch_ttl_seconds,
            json.dumps(snapshot, ensure_ascii=False),
        )

    def mark_event_seen(self, event: TicketEvent) -> bool:
        digest = hashlib.sha256(event.signature.encode("utf-8")).hexdigest()
        key = f"ticket_notifications:event:{event.ticket_id}:{digest}"
        return bool(
            self.redis_client.set(
                key,
                json.dumps(event.to_dict(), ensure_ascii=False),
                nx=True,
                ex=self.recent_events_ttl_seconds,
            )
        )

    def mark_events_baseline(self, events: Iterable[TicketEvent]) -> None:
        for event in events:
            self.mark_event_seen(event)

    def acquire_poll_lock(self, timeout_seconds: int = 25):
        return self.redis_client.lock(
            self.LOCK_KEY,
            timeout=timeout_seconds,
            blocking_timeout=1,
        )

    def force_release_poll_lock(self) -> None:
        self.redis_client.delete(self.LOCK_KEY)

    @staticmethod
    def _ticket_key(ticket_id: int) -> str:
        return f"ticket_notifications:ticket:{ticket_id}"

    @staticmethod
    def _snapshot_key(ticket_id: int) -> str:
        return f"ticket_notifications:snapshot:{ticket_id}"
