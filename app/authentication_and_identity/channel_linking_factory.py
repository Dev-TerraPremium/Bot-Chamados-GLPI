from app.application_config.settings import AppSettings
from app.authentication_and_identity.channel_linking_service import ChannelLinkingService
from app.authentication_and_identity.redis_channel_identity_link_store import RedisChannelIdentityLinkStore
from app.authentication_and_identity.channel_link_audit_service import ChannelLinkAuditService
from app.authentication_and_identity.glpi_user_identity_lookup_service import MockGLPIUserIdentityLookupService
from app.distributed_runtime.redis_connection import get_redis_client

class InMemoryChannelIdentityLinkStore(RedisChannelIdentityLinkStore):
    """
    Simples mock store in memory para testes. 
    Herdamos só para usar a mesma interface.
    """
    def __init__(self):
        self.data = {}

    def save(self, link) -> None:
        key = f"{link.channel}:{link.channel_identifier}"
        self.data[key] = link

    def get(self, channel: str, channel_identifier: str):
        key = f"{channel}:{channel_identifier}"
        return self.data.get(key)

    def delete(self, channel: str, channel_identifier: str) -> None:
        key = f"{channel}:{channel_identifier}"
        self.data.pop(key, None)

class MockChannelLinkAuditService(ChannelLinkAuditService):
    def __init__(self):
        self.logs = []
        
    def _log_event(self, event_type: str, channel: str, channel_identifier_masked: str, details: dict):
        self.logs.append({
            "event_type": event_type,
            "channel": channel,
            "channel_identifier_masked": channel_identifier_masked,
            "details": details
        })

def build_channel_linking_service(settings: AppSettings) -> ChannelLinkingService:
    if settings.channel_linking_mode == "redis" or settings.is_redis_state_enabled:
        redis_client = get_redis_client(settings.redis_url)
        store = RedisChannelIdentityLinkStore(
            redis_client=redis_client,
            active_ttl_seconds=settings.channel_link_active_ttl_seconds,
            pending_ttl_seconds=settings.channel_link_pending_ttl_seconds
        )
        audit_service = ChannelLinkAuditService(redis_client, audit_ttl_seconds=settings.channel_link_audit_ttl_seconds)
    else:
        store = InMemoryChannelIdentityLinkStore()
        audit_service = MockChannelLinkAuditService()
        
    lookup_service = MockGLPIUserIdentityLookupService()
    
    return ChannelLinkingService(
        store=store,
        audit_service=audit_service,
        lookup_service=lookup_service,
        pepper=settings.channel_link_hmac_pepper,
        prefix_length=settings.channel_link_cpf_prefix_length,
        max_attempts=settings.channel_link_max_failed_attempts,
        allow_web_simulator_auto_user=settings.channel_link_allow_web_simulator_auto_user
    )
