from time import time

from redis import Redis


class RedisRateLimiter:
    def __init__(
        self,
        redis_client: Redis,
        max_messages_per_minute: int = 20,
        max_messages_per_hour: int = 200,
    ) -> None:
        self.redis_client = redis_client
        self.max_messages_per_minute = max_messages_per_minute
        self.max_messages_per_hour = max_messages_per_hour

    def allow_message(self, identity: str) -> bool:
        now = int(time())
        minute_key = f"ratelimit:minute:{identity}:{now // 60}"
        hour_key = f"ratelimit:hour:{identity}:{now // 3600}"

        pipe = self.redis_client.pipeline()
        pipe.incr(minute_key)
        pipe.expire(minute_key, 90)
        pipe.incr(hour_key)
        pipe.expire(hour_key, 3900)
        minute_count, _, hour_count, _ = pipe.execute()

        return (
            int(minute_count) <= self.max_messages_per_minute
            and int(hour_count) <= self.max_messages_per_hour
        )

    def reset(self, identity: str) -> None:
        pattern_keys = []
        for pattern in (
            f"ratelimit:minute:{identity}:*",
            f"ratelimit:hour:{identity}:*",
        ):
            pattern_keys.extend(self.redis_client.keys(pattern))
        if pattern_keys:
            self.redis_client.delete(*pattern_keys)
