from app.application_config.settings import AppSettings
from app.distributed_runtime.idempotency_store import (
    InMemoryIdempotencyStore,
    RedisIdempotencyStore,
)
from app.distributed_runtime.redis_connection import get_redis_client
from app.distributed_runtime.redis_conversation_store import RedisConversationStore
from app.distributed_runtime.redis_rate_limiter import RedisRateLimiter
from app.distributed_runtime.session_locks import NoOpSessionLock, RedisSessionLock
from app.security_and_abuse_protection.simple_rate_limiter import SimpleRateLimiter
from app.simulated_persistence.in_memory_conversation_store import (
    InMemoryConversationStore,
)


def build_conversation_store(settings: AppSettings):
    if settings.is_redis_state_enabled:
        return RedisConversationStore(
            get_redis_client(settings.redis_url),
            ttl_seconds=settings.session_ttl_seconds,
        )
    return InMemoryConversationStore()


def build_rate_limiter(settings: AppSettings):
    if settings.is_redis_state_enabled:
        return RedisRateLimiter(
            get_redis_client(settings.redis_url),
            max_messages_per_minute=settings.rate_limit_messages_per_minute,
            max_messages_per_hour=settings.rate_limit_messages_per_hour,
        )
    return SimpleRateLimiter(settings.rate_limit_messages_per_minute)


def build_session_lock(settings: AppSettings):
    if settings.is_redis_state_enabled:
        return RedisSessionLock(
            get_redis_client(settings.redis_url),
            timeout_seconds=settings.session_lock_timeout_seconds,
        )
    return NoOpSessionLock()


def build_idempotency_store(settings: AppSettings):
    ttl_seconds = settings.glpi_create_ticket_idempotency_ttl_seconds
    if settings.is_redis_state_enabled:
        return RedisIdempotencyStore(
            get_redis_client(settings.redis_url),
            ttl_seconds=ttl_seconds,
        )
    return InMemoryIdempotencyStore(ttl_seconds=ttl_seconds)
