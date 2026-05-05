from contextlib import contextmanager
from typing import Iterator

from redis import Redis


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
            blocking_timeout=self.timeout_seconds,
        )
        acquired = lock.acquire(blocking=True)
        if not acquired:
            raise RuntimeError("Nao foi possivel obter lock da conversa.")
        try:
            yield
        finally:
            lock.release()
