import fakeredis

from app.authentication_and_identity.authenticated_user_model import AuthenticatedUser
from app.conversation_engine.conversation_context import ConversationContext
from app.distributed_runtime.idempotency_store import RedisIdempotencyStore
from app.distributed_runtime.redis_conversation_store import RedisConversationStore
from app.distributed_runtime.redis_rate_limiter import RedisRateLimiter


def test_redis_conversation_store_round_trips_context() -> None:
    redis_client = fakeredis.FakeRedis(decode_responses=True)
    store = RedisConversationStore(redis_client, ttl_seconds=60)
    context = ConversationContext(
        session_id="s1",
        channel="web_simulator",
        user=AuthenticatedUser(
            full_name="Pedro Torres",
            login="pedro.torres",
            email="pedro.torres@empresa.local",
            glpi_user_id=266,
        ),
    )
    context.selected_category_id = 11
    context.selected_category_name = "Ubiquiti / Wi-Fi"

    store.save(context)
    loaded = store.get("s1")

    assert loaded is not None
    assert loaded.selected_category_name == "Ubiquiti / Wi-Fi"
    assert loaded.user.glpi_user_id == 266


def test_redis_rate_limiter_blocks_after_limit() -> None:
    redis_client = fakeredis.FakeRedis(decode_responses=True)
    limiter = RedisRateLimiter(
        redis_client,
        max_messages_per_minute=2,
        max_messages_per_hour=10,
    )

    assert limiter.allow_message("s1")
    assert limiter.allow_message("s1")
    assert not limiter.allow_message("s1")


def test_redis_idempotency_store_prevents_duplicate_reservation() -> None:
    redis_client = fakeredis.FakeRedis(decode_responses=True)
    store = RedisIdempotencyStore(redis_client, ttl_seconds=60)

    assert store.reserve("abc")
    assert not store.reserve("abc")
    assert store.get_result("abc") is None

    store.store_result("abc", {"ticket_number": 123})
    assert store.get_result("abc") == {"ticket_number": 123}
