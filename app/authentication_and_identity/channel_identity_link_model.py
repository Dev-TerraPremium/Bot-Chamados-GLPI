import datetime
from enum import Enum
from typing import Any

class ChannelIdentityLinkStatus(str, Enum):
    PENDING = "pending"
    ACTIVE = "active"
    BLOCKED = "blocked"
    REVOKED = "revoked"

class ChannelIdentityLink:
    def __init__(
        self,
        channel: str,
        channel_identifier: str,
        status: ChannelIdentityLinkStatus,
        glpi_user_id: int | None = None,
        glpi_login: str | None = None,
        display_name: str | None = None,
        email: str | None = None,
        cpf_partial_hmac: str | None = None,
        failed_attempts: int = 0,
        unlock_required: bool = False,
        verified_at: str | None = None,
        verified_by: str | None = None,
        created_at: str | None = None,
        updated_at: str | None = None,
        revoked_at: str | None = None,
        revoked_by: str | None = None,
        revoke_reason: str | None = None,
    ):
        self.channel = channel
        self.channel_identifier = channel_identifier
        self.status = status
        self.glpi_user_id = glpi_user_id
        self.glpi_login = glpi_login
        self.display_name = display_name
        self.email = email
        self.cpf_partial_hmac = cpf_partial_hmac
        self.failed_attempts = failed_attempts
        self.unlock_required = unlock_required
        self.verified_at = verified_at
        self.verified_by = verified_by
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        self.created_at = created_at or now
        self.updated_at = updated_at or now
        self.revoked_at = revoked_at
        self.revoked_by = revoked_by
        self.revoke_reason = revoke_reason

    def to_dict(self) -> dict[str, Any]:
        return {
            "channel": self.channel,
            "channel_identifier": self.channel_identifier,
            "status": self.status.value,
            "glpi_user_id": self.glpi_user_id,
            "glpi_login": self.glpi_login,
            "display_name": self.display_name,
            "email": self.email,
            "cpf_partial_hmac": self.cpf_partial_hmac,
            "failed_attempts": self.failed_attempts,
            "unlock_required": self.unlock_required,
            "verified_at": self.verified_at,
            "verified_by": self.verified_by,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "revoked_at": self.revoked_at,
            "revoked_by": self.revoked_by,
            "revoke_reason": self.revoke_reason,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ChannelIdentityLink":
        return cls(
            channel=data["channel"],
            channel_identifier=data["channel_identifier"],
            status=ChannelIdentityLinkStatus(data["status"]),
            glpi_user_id=data.get("glpi_user_id"),
            glpi_login=data.get("glpi_login"),
            display_name=data.get("display_name"),
            email=data.get("email"),
            cpf_partial_hmac=data.get("cpf_partial_hmac"),
            failed_attempts=data.get("failed_attempts", 0),
            unlock_required=data.get("unlock_required", False),
            verified_at=data.get("verified_at"),
            verified_by=data.get("verified_by"),
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
            revoked_at=data.get("revoked_at"),
            revoked_by=data.get("revoked_by"),
            revoke_reason=data.get("revoke_reason"),
        )
