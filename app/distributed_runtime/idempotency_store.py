import json
from time import monotonic
from typing import Any

from redis import Redis


class InMemoryIdempotencyStore:
    def __init__(self, ttl_seconds: int = 300) -> None:
        self.ttl_seconds = ttl_seconds
        self._items: dict[str, tuple[float, dict[str, Any] | None]] = {}

    def get_result(self, key: str) -> dict[str, Any] | None:
        self._cleanup()
        item = self._items.get(key)
        if not item:
            return None
        _, result = item
        return result

    def reserve(self, key: str) -> bool:
        self._cleanup()
        if key in self._items:
            return False
        self._items[key] = (monotonic() + self.ttl_seconds, None)
        return True

    def store_result(self, key: str, result: dict[str, Any]) -> None:
        self._items[key] = (monotonic() + self.ttl_seconds, result)

    def release(self, key: str) -> None:
        item = self._items.get(key)
        if item and item[1] is None:
            self._items.pop(key, None)

    def clear(self, key_prefix: str) -> None:
        for key in list(self._items):
            if key.startswith(key_prefix):
                self._items.pop(key, None)

    def _cleanup(self) -> None:
        now = monotonic()
        for key, (expires_at, _) in list(self._items.items()):
            if expires_at <= now:
                self._items.pop(key, None)


class RedisIdempotencyStore:
    def __init__(self, redis_client: Redis, ttl_seconds: int = 300) -> None:
        self.redis_client = redis_client
        self.ttl_seconds = ttl_seconds

    def _key(self, key: str) -> str:
        return f"ticket_idempotency:{key}"

    def get_result(self, key: str) -> dict[str, Any] | None:
        raw_value = self.redis_client.get(self._key(key))
        if not raw_value or raw_value == "__reserved__":
            return None
        return json.loads(raw_value)

    def reserve(self, key: str) -> bool:
        return bool(
            self.redis_client.set(
                self._key(key),
                "__reserved__",
                ex=self.ttl_seconds,
                nx=True,
            )
        )

    def store_result(self, key: str, result: dict[str, Any]) -> None:
        self.redis_client.setex(
            self._key(key),
            self.ttl_seconds,
            json.dumps(result, ensure_ascii=False, separators=(",", ":")),
        )

    def release(self, key: str) -> None:
        redis_key = self._key(key)
        if self.redis_client.get(redis_key) == "__reserved__":
            self.redis_client.delete(redis_key)

    def clear(self, key_prefix: str) -> None:
        keys = self.redis_client.keys(self._key(f"{key_prefix}*"))
        if keys:
            self.redis_client.delete(*keys)
