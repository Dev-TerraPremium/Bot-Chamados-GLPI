import json
import logging
from datetime import datetime, timezone
from enum import Enum
from redis import Redis

logger = logging.getLogger(__name__)

class ChannelLinkAuditService:
    def __init__(self, redis_client: Redis, audit_ttl_seconds: int = 31536000):
        self.redis_client = redis_client
        self.audit_ttl_seconds = audit_ttl_seconds
        self.key_prefix = "channel_link_audit:"

    def _log_event(self, event_type: str, channel: str, channel_identifier_masked: str, details: dict):
        timestamp = datetime.now(timezone.utc).isoformat()
        log_entry = {
            "timestamp": timestamp,
            "event_type": event_type,
            "channel": channel,
            "channel_identifier_masked": channel_identifier_masked,
            "details": details
        }
        
        # Log to standard output/file
        logger.info(f"Audit [{event_type}]: {json.dumps(log_entry)}")
        
        # Save to Redis
        try:
            key = f"{self.key_prefix}{channel}:{channel_identifier_masked}"
            self.redis_client.lpush(key, json.dumps(log_entry))
            self.redis_client.expire(key, self.audit_ttl_seconds)
            # keep max 100 entries
            self.redis_client.ltrim(key, 0, 99)
        except Exception as e:
            logger.error(f"Failed to write audit log to Redis: {e}", exc_info=True)

    def log_link_attempt(self, channel: str, channel_identifier_masked: str):
        self._log_event("LINK_ATTEMPT", channel, channel_identifier_masked, {})

    def log_link_created(self, channel: str, channel_identifier_masked: str, glpi_user_id: int):
        self._log_event("LINK_CREATED", channel, channel_identifier_masked, {"glpi_user_id": glpi_user_id})

    def log_cpf_failure(self, channel: str, channel_identifier_masked: str, failed_attempts: int):
        self._log_event("CPF_FAILURE", channel, channel_identifier_masked, {"failed_attempts": failed_attempts})

    def log_ambiguity(self, channel: str, channel_identifier_masked: str, candidates_count: int):
        self._log_event("AMBIGUITY", channel, channel_identifier_masked, {"candidates_count": candidates_count})

    def log_channel_blocked(self, channel: str, channel_identifier_masked: str):
        self._log_event("CHANNEL_BLOCKED", channel, channel_identifier_masked, {})

    def log_admin_unlock(self, channel: str, channel_identifier_masked: str, admin_user: str, reason: str):
        self._log_event("ADMIN_UNLOCK", channel, channel_identifier_masked, {"admin_user": admin_user, "reason": reason})

    def log_link_revoked(self, channel: str, channel_identifier_masked: str, admin_user: str, reason: str):
        self._log_event("LINK_REVOKED", channel, channel_identifier_masked, {"admin_user": admin_user, "reason": reason})
