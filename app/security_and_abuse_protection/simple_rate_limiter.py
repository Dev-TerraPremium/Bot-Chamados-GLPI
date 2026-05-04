from collections import defaultdict, deque
from time import monotonic


class SimpleRateLimiter:
    def __init__(self, max_messages_per_minute: int = 20) -> None:
        self.max_messages_per_minute = max_messages_per_minute
        self._events_by_session: dict[str, deque[float]] = defaultdict(deque)

    def allow_message(self, session_id: str) -> bool:
        now = monotonic()
        events = self._events_by_session[session_id]

        while events and now - events[0] > 60:
            events.popleft()

        if len(events) >= self.max_messages_per_minute:
            return False

        events.append(now)
        return True

    def reset(self, session_id: str) -> None:
        self._events_by_session.pop(session_id, None)

