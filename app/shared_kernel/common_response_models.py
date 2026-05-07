from typing import Any

from pydantic import BaseModel, Field

from app.shared_kernel.constants import DEFAULT_CHANNEL


class AttachmentPayload(BaseModel):
    mime_type: str
    file_name: str
    base64_data: str


class ConversationMessageRequest(BaseModel):
    session_id: str = Field(default="", max_length=120)
    channel: str = Field(default=DEFAULT_CHANNEL, max_length=40)
    channel_identifier: str = Field(default="", max_length=255)
    message: str = Field(default="", max_length=5000)
    media: list[AttachmentPayload] | None = None


class ConversationMessageResponse(BaseModel):
    session_id: str
    bot_message: str
    state: str
    ticket_preview: dict[str, Any] | None = None
    created_ticket: dict[str, Any] | None = None


class HealthResponse(BaseModel):
    status: str
    app_name: str
    environment: str
    glpi_integration_mode: str
