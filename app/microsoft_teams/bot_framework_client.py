from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from urllib.parse import quote

import httpx

from app.application_config.settings import AppSettings
from app.microsoft_teams.conversation_reference_store import TeamsConversationReference

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class TeamsSendResult:
    ok: bool
    status_code: int = 0
    detail: str = ""


class TeamsBotFrameworkClient:
    TOKEN_URL = "https://login.microsoftonline.com/botframework.com/oauth2/v2.0/token"
    TOKEN_SCOPE = "https://api.botframework.com/.default"

    def __init__(self, settings: AppSettings) -> None:
        self.settings = settings
        self._access_token = ""
        self._access_token_expires_at = 0.0

    def send_activity(
        self,
        reference: TeamsConversationReference,
        *,
        text: str = "",
        attachments: list[dict] | None = None,
        reply_to_activity_id: str = "",
    ) -> TeamsSendResult:
        if not self.settings.teams_app_id or not self.settings.teams_app_password:
            logger.info("teams_connector_not_configured")
            return TeamsSendResult(ok=False, detail="teams_not_configured")

        endpoint = self._activity_endpoint(reference, reply_to_activity_id)
        body = {
            "type": "message",
            "channelId": reference.channel_id,
            "conversation": {"id": reference.conversation_id},
            "recipient": {"id": reference.user_id},
            "from": {"id": reference.bot_id},
            "text": text,
        }
        if attachments:
            body["attachments"] = attachments

        try:
            response = httpx.post(
                endpoint,
                json=body,
                headers={"Authorization": f"Bearer {self._get_access_token()}"},
                timeout=self.settings.teams_connector_timeout_seconds,
            )
        except httpx.HTTPError as exc:
            logger.warning("teams_send_activity_error", extra={"error": str(exc)})
            return TeamsSendResult(ok=False, detail=str(exc))

        if 200 <= response.status_code < 300:
            return TeamsSendResult(ok=True, status_code=response.status_code)

        logger.warning(
            "teams_send_activity_failed",
            extra={"status_code": response.status_code, "body": response.text[:500]},
        )
        return TeamsSendResult(
            ok=False,
            status_code=response.status_code,
            detail=response.text[:500],
        )

    def _get_access_token(self) -> str:
        now = time.time()
        if self._access_token and now < self._access_token_expires_at - 60:
            return self._access_token

        response = httpx.post(
            self.TOKEN_URL,
            data={
                "grant_type": "client_credentials",
                "client_id": self.settings.teams_app_id,
                "client_secret": self.settings.teams_app_password,
                "scope": self.TOKEN_SCOPE,
            },
            timeout=self.settings.teams_connector_timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
        self._access_token = str(payload["access_token"])
        self._access_token_expires_at = now + int(payload.get("expires_in") or 3600)
        return self._access_token

    @staticmethod
    def _activity_endpoint(
        reference: TeamsConversationReference,
        reply_to_activity_id: str,
    ) -> str:
        base_url = reference.service_url.rstrip("/")
        conversation_id = quote(reference.conversation_id, safe="")
        if reply_to_activity_id:
            activity_id = quote(reply_to_activity_id, safe="")
            return f"{base_url}/v3/conversations/{conversation_id}/activities/{activity_id}"
        return f"{base_url}/v3/conversations/{conversation_id}/activities"
