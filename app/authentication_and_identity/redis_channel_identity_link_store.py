import json
import logging
from redis import Redis
from app.authentication_and_identity.channel_identity_link_model import ChannelIdentityLink, ChannelIdentityLinkStatus
from app.authentication_and_identity.channel_identity_link_store_interface import ChannelIdentityLinkStoreInterface

logger = logging.getLogger(__name__)

class RedisChannelIdentityLinkStore(ChannelIdentityLinkStoreInterface):
    def __init__(
        self, 
        redis_client: Redis, 
        active_ttl_seconds: int = 0,
        pending_ttl_seconds: int = 900
    ):
        self.redis_client = redis_client
        self.active_ttl_seconds = active_ttl_seconds
        self.pending_ttl_seconds = pending_ttl_seconds
        self.key_prefix = "channel_link:"

    def _build_key(self, channel: str, channel_identifier: str) -> str:
        return f"{self.key_prefix}{channel}:{channel_identifier}"

    def save(self, link: ChannelIdentityLink) -> None:
        key = self._build_key(link.channel, link.channel_identifier)
        try:
            data = json.dumps(link.to_dict())
            
            ttl = 0
            if link.status == ChannelIdentityLinkStatus.PENDING:
                ttl = self.pending_ttl_seconds
            elif link.status == ChannelIdentityLinkStatus.ACTIVE and self.active_ttl_seconds > 0:
                ttl = self.active_ttl_seconds
                
            if ttl > 0:
                self.redis_client.setex(key, ttl, data)
            else:
                self.redis_client.set(key, data)
        except Exception as e:
            logger.error(f"Failed to save channel identity link to Redis: {e}", exc_info=True)

    def get(self, channel: str, channel_identifier: str) -> ChannelIdentityLink | None:
        key = self._build_key(channel, channel_identifier)
        try:
            data = self.redis_client.get(key)
            if not data:
                return None
            return ChannelIdentityLink.from_dict(json.loads(data))
        except Exception as e:
            logger.error(f"Failed to load channel identity link from Redis: {e}", exc_info=True)
            return None

    def delete(self, channel: str, channel_identifier: str) -> None:
        key = self._build_key(channel, channel_identifier)
        try:
            self.redis_client.delete(key)
        except Exception as e:
            logger.error(f"Failed to delete channel identity link from Redis: {e}", exc_info=True)
