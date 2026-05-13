from __future__ import annotations

import json
from dataclasses import asdict, dataclass

from redis import Redis


@dataclass(frozen=True, slots=True)
class TeamsConversationReference:
    channel_identifier: str
    service_url: str
    conversation_id: str
    user_id: str
    bot_id: str
    tenant_id: str
    channel_id: str = "msteams"


class TeamsConversationReferenceStore:
    def __init__(self, redis_client: Redis, ttl_seconds: int = 31536000) -> None:
        self.redis_client = redis_client
        self.ttl_seconds = ttl_seconds

    def save_from_activity(self, channel_identifier: str, activity: dict) -> None:
        reference = self.reference_from_activity(channel_identifier, activity)
        if reference is None:
            return
        self.save(reference)

    def save(self, reference: TeamsConversationReference) -> None:
        self.redis_client.setex(
            self._key(reference.channel_identifier),
            self.ttl_seconds,
            json.dumps(asdict(reference), ensure_ascii=False),
        )

    def get(self, channel_identifier: str) -> TeamsConversationReference | None:
        raw_value = self.redis_client.get(self._key(channel_identifier))
        if not raw_value:
            return None
        data = json.loads(raw_value)
        return TeamsConversationReference(**data)

    @staticmethod
    def reference_from_activity(
        channel_identifier: str,
        activity: dict,
    ) -> TeamsConversationReference | None:
        conversation = activity.get("conversation") or {}
        sender = activity.get("from") or {}
        recipient = activity.get("recipient") or {}
        channel_data = activity.get("channelData") or {}
        tenant = channel_data.get("tenant") or {}
        service_url = str(activity.get("serviceUrl") or "").strip()
        conversation_id = str(conversation.get("id") or "").strip()
        user_id = str(sender.get("id") or "").strip()
        bot_id = str(recipient.get("id") or "").strip()
        if not service_url or not conversation_id or not user_id or not bot_id:
            return None
        return TeamsConversationReference(
            channel_identifier=channel_identifier,
            service_url=service_url,
            conversation_id=conversation_id,
            user_id=user_id,
            bot_id=bot_id,
            tenant_id=str(tenant.get("id") or "").strip(),
            channel_id=str(activity.get("channelId") or "msteams"),
        )

    @staticmethod
    def _key(channel_identifier: str) -> str:
        return f"teams:conversation_reference:{channel_identifier}"
