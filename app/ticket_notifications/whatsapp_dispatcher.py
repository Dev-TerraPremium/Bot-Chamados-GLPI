from __future__ import annotations

import logging
from dataclasses import dataclass

import httpx

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class WhatsAppSendResult:
    ok: bool
    status_code: int = 0
    error: str = ""


class WhatsAppNotificationDispatcher:
    def __init__(
        self,
        *,
        base_url: str,
        internal_token: str,
        timeout_seconds: float = 5.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.internal_token = internal_token
        self.timeout_seconds = timeout_seconds

    @property
    def is_configured(self) -> bool:
        return bool(self.base_url and self.internal_token)

    def send_message(self, phone: str, message: str) -> WhatsAppSendResult:
        if not self.is_configured:
            logger.info("ticket_notification_whatsapp_dispatcher_not_configured")
            return WhatsAppSendResult(ok=False, error="not_configured")
        if not phone or not message.strip():
            return WhatsAppSendResult(ok=False, error="empty_phone_or_message")

        try:
            response = httpx.post(
                f"{self.base_url}/internal/send-message",
                headers={"X-Internal-Token": self.internal_token},
                json={"phone": phone, "message": message},
                timeout=self.timeout_seconds,
            )
            if 200 <= response.status_code < 300:
                return WhatsAppSendResult(ok=True, status_code=response.status_code)
            logger.warning(
                "ticket_notification_whatsapp_dispatch_failed",
                extra={"status_code": response.status_code},
            )
            return WhatsAppSendResult(ok=False, status_code=response.status_code)
        except httpx.HTTPError as exc:
            logger.warning(
                "ticket_notification_whatsapp_dispatch_error",
                extra={"error": str(exc)},
            )
            return WhatsAppSendResult(ok=False, error=str(exc))
