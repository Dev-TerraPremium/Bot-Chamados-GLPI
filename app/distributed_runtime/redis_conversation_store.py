import json

from redis import Redis

from app.conversation_engine.conversation_context import ConversationContext
from app.distributed_runtime.conversation_context_codec import ConversationContextCodec


class RedisConversationStore:
    def __init__(self, redis_client: Redis, ttl_seconds: int = 3600) -> None:
        self.redis_client = redis_client
        self.ttl_seconds = ttl_seconds

    def _key(self, session_id: str) -> str:
        return f"conversation:{session_id}"

    def get(self, session_id: str) -> ConversationContext | None:
        raw_value = self.redis_client.get(self._key(session_id))
        if not raw_value:
            return None
        return ConversationContextCodec.from_dict(json.loads(raw_value))

    def save(self, context: ConversationContext) -> None:
        payload = json.dumps(
            ConversationContextCodec.to_dict(context),
            ensure_ascii=False,
            separators=(",", ":"),
        )
        self.redis_client.setex(self._key(context.session_id), self.ttl_seconds, payload)

    def delete(self, session_id: str) -> None:
        self.redis_client.delete(self._key(session_id))

    def debug_context(self, session_id: str) -> dict | None:
        context = self.get(session_id)
        if context is None:
            return None
        return context.to_safe_dict()
