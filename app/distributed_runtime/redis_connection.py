from functools import lru_cache

from redis import Redis

from app.application_config.settings import load_settings


@lru_cache(maxsize=4)
def get_redis_client(url: str | None = None) -> Redis:
    settings = load_settings()
    redis_url = url or settings.redis_url
    return Redis.from_url(redis_url, decode_responses=True)
