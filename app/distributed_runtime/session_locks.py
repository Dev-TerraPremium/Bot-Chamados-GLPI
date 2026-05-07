from contextlib import contextmanager
from typing import Iterator

from redis import Redis
from redis.exceptions import LockError, RedisError


class BusySessionError(RuntimeError):
    pass


class NoOpSessionLock:
    @contextmanager
    def lock(self, session_id: str) -> Iterator[None]:
        yield


class RedisSessionLock:
    def __init__(self, redis_client: Redis, timeout_seconds: int = 30) -> None:
        self.redis_client = redis_client
        self.timeout_seconds = timeout_seconds

    @contextmanager
    def lock(self, session_id: str) -> Iterator[None]:
        lock = self.redis_client.lock(
            f"lock:conversation:{session_id}",
            timeout=self.timeout_seconds,
            blocking_timeout=0,
        )
        acquired = lock.acquire(blocking=False)
        if not acquired:
            raise BusySessionError("Conversa ja esta em processamento.")
        try:
            yield
        finally:
            try:
                lock.release()
            except (LockError, RedisError):
                pass
