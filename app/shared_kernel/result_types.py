from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class ConversationTurnResult:
    session_id: str
    bot_message: str
    state: str
    bot_messages: list[str] | None = None
    ticket_preview: dict[str, Any] | None = None
    created_ticket: dict[str, Any] | None = None


@dataclass(slots=True)
class OperationResult:
    success: bool
    message: str
    data: dict[str, Any] = field(default_factory=dict)
