from dataclasses import dataclass
from typing import Any
import datetime

from app.authentication_and_identity.channel_identity_link_model import ChannelIdentityLinkStatus
from app.authentication_and_identity.channel_identity_link_store_interface import ChannelIdentityLinkStoreInterface
from app.authentication_and_identity.channel_link_audit_service import ChannelLinkAuditService
from app.authentication_and_identity.channel_identifier_normalizer import ChannelIdentifierNormalizer

@dataclass
class AdminUnlockResult:
    success: bool
    message: str

class AdminChannelUnlockService:
    def __init__(
        self, 
        store: ChannelIdentityLinkStoreInterface,
        audit_service: ChannelLinkAuditService
    ):
        self.store = store
        self.audit_service = audit_service

    def block_link(self, channel: str, channel_identifier: str, admin_user: str, reason: str) -> AdminUnlockResult:
        normalized_id = ChannelIdentifierNormalizer.normalize_phone(channel_identifier)
        link = self.store.get(channel, normalized_id)
        if not link:
            return AdminUnlockResult(False, "Link not found")
        
        link.status = ChannelIdentityLinkStatus.BLOCKED
        link.unlock_required = True
        link.updated_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
        self.store.save(link)
        
        masked = ChannelIdentifierNormalizer.mask_phone(normalized_id)
        self.audit_service.log_channel_blocked(channel, masked)
        
        return AdminUnlockResult(True, "Channel blocked successfully")

    def unlock_link(self, channel: str, channel_identifier: str, admin_user: str, reason: str) -> AdminUnlockResult:
        normalized_id = ChannelIdentifierNormalizer.normalize_phone(channel_identifier)
        link = self.store.get(channel, normalized_id)
        if not link:
            return AdminUnlockResult(False, "Link not found")
            
        if link.status != ChannelIdentityLinkStatus.BLOCKED:
            return AdminUnlockResult(False, "Link is not blocked")
            
        link.status = ChannelIdentityLinkStatus.ACTIVE
        link.failed_attempts = 0
        link.unlock_required = False
        link.updated_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
        self.store.save(link)
        
        masked = ChannelIdentifierNormalizer.mask_phone(normalized_id)
        self.audit_service.log_admin_unlock(channel, masked, admin_user, reason)
        
        return AdminUnlockResult(True, "Channel unlocked successfully")

    def revoke_link(self, channel: str, channel_identifier: str, admin_user: str, reason: str) -> AdminUnlockResult:
        normalized_id = ChannelIdentifierNormalizer.normalize_phone(channel_identifier)
        link = self.store.get(channel, normalized_id)
        if not link:
            return AdminUnlockResult(False, "Link not found")
            
        link.status = ChannelIdentityLinkStatus.REVOKED
        link.revoked_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
        link.revoked_by = admin_user
        link.revoke_reason = reason
        link.updated_at = link.revoked_at
        self.store.save(link)
        
        masked = ChannelIdentifierNormalizer.mask_phone(normalized_id)
        self.audit_service.log_link_revoked(channel, masked, admin_user, reason)
        
        return AdminUnlockResult(True, "Channel link revoked successfully")

    def relink_channel(self, channel: str, channel_identifier: str, glpi_user_id: int, admin_user: str, reason: str) -> AdminUnlockResult:
        # A relink might be complex if we need user data.
        # For simplicity, we just revoke the old one and clear it, letting user re-validate, 
        # or we could forcibly set the link.
        self.delete_link(channel, channel_identifier)
        return AdminUnlockResult(True, "Channel relink prepared, user should authenticate again")
        
    def delete_link(self, channel: str, channel_identifier: str) -> None:
        normalized_id = ChannelIdentifierNormalizer.normalize_phone(channel_identifier)
        self.store.delete(channel, normalized_id)
