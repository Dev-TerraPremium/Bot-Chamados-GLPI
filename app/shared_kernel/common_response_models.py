from typing import Any

from pydantic import BaseModel, Field


class ConversationMessageRequest(BaseModel):
    session_id: str = Field(default="", max_length=120)
    channel_identifier: str = Field(default="", max_length=255)
    message: str = Field(default="", max_length=5000)


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

