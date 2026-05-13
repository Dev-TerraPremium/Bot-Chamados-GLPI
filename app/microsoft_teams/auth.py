from __future__ import annotations

import logging

import httpx
from fastapi import HTTPException

from app.application_config.settings import AppSettings

logger = logging.getLogger(__name__)


class TeamsBotFrameworkAuthenticator:
    OPENID_METADATA_URL = "https://login.botframework.com/v1/.well-known/openidconfiguration"
    VALID_ISSUERS = {"https://api.botframework.com"}

    def __init__(self, settings: AppSettings) -> None:
        self.settings = settings
        self._jwks_uri = ""

    def validate_authorization_header(self, authorization: str | None) -> None:
        if not self.settings.teams_auth_validation_enabled:
            return
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="missing_bot_framework_token")

        try:
            import jwt
        except ImportError as exc:
            logger.exception("teams_auth_dependency_missing")
            raise HTTPException(status_code=500, detail="teams_auth_dependency_missing") from exc

        token = authorization.removeprefix("Bearer ").strip()
        try:
            signing_key = jwt.PyJWKClient(self._get_jwks_uri()).get_signing_key_from_jwt(token)
            payload = jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256"],
                audience=self.settings.teams_app_id,
                options={"require": ["aud", "iss", "exp"]},
            )
        except Exception as exc:
            logger.warning("teams_auth_token_invalid", extra={"error": str(exc)})
            raise HTTPException(status_code=401, detail="invalid_bot_framework_token") from exc

        issuer = str(payload.get("iss") or "")
        if issuer not in self.VALID_ISSUERS:
            raise HTTPException(status_code=401, detail="invalid_bot_framework_issuer")

    def _get_jwks_uri(self) -> str:
        if self._jwks_uri:
            return self._jwks_uri
        response = httpx.get(
            self.OPENID_METADATA_URL,
            timeout=self.settings.teams_connector_timeout_seconds,
        )
        response.raise_for_status()
        self._jwks_uri = str(response.json()["jwks_uri"])
        return self._jwks_uri
