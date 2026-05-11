from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.shared_kernel.constants import DEFAULT_CHANNEL


class AttachmentPayload(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    mime_type: str
    file_name: str
    data_base64: str = Field(alias="base64_data")

    def to_context_dict(self) -> dict[str, str]:
        return {
            "mime_type": self.mime_type,
            "file_name": self.file_name,
            "data_base64": self.data_base64,
        }


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
    bot_messages: list[str] | None = None
    ticket_preview: dict[str, Any] | None = None
    created_ticket: dict[str, Any] | None = None


class HealthResponse(BaseModel):
    status: str
    app_name: str
    environment: str
    glpi_integration_mode: str
