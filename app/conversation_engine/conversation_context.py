from dataclasses import dataclass
from typing import Any

from app.authentication_and_identity.authenticated_user_model import AuthenticatedUser
from app.conversation_engine.conversation_states import ConversationState


@dataclass(slots=True)
class ConversationContext:
    session_id: str
    channel: str
    user: AuthenticatedUser
    state: ConversationState = ConversationState.MAIN_MENU
    opening_mode: str | None = None
    selected_category_id: int | None = None
    selected_category_name: str | None = None
    pending_category_suggestion_id: int | None = None
    pending_category_suggestion_name: str | None = None
    original_description: str | None = None
    organized_description: str | None = None
    impact_id: int | None = None
    impact_label: str | None = None
    severity: str | None = None
    location: str | None = None
    evidence: str | None = None
    suggested_title: str | None = None
    ticket_preview: dict[str, Any] | None = None
    ticket_to_complement_id: int | None = None
    complement_original_text: str | None = None
    complement_rewritten_text: str | None = None

    def reset_ticket_draft(self) -> None:
        self.opening_mode = None
        self.selected_category_id = None
        self.selected_category_name = None
        self.pending_category_suggestion_id = None
        self.pending_category_suggestion_name = None
        self.original_description = None
        self.organized_description = None
        self.impact_id = None
        self.impact_label = None
        self.severity = None
        self.location = None
        self.evidence = None
        self.suggested_title = None
        self.ticket_preview = None
        self.reset_complement()

    def reset_complement(self) -> None:
        self.ticket_to_complement_id = None
        self.complement_original_text = None
        self.complement_rewritten_text = None

    def move_to_main_menu(self) -> None:
        self.reset_ticket_draft()
        self.state = ConversationState.MAIN_MENU

    def to_safe_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "channel": self.channel,
            "user": self.user.to_safe_dict(),
            "state": self.state.value,
            "opening_mode": self.opening_mode,
            "selected_category_id": self.selected_category_id,
            "selected_category_name": self.selected_category_name,
            "impact_id": self.impact_id,
            "impact_label": self.impact_label,
            "severity": self.severity,
            "location": self.location,
            "evidence_informed": bool(self.evidence and self.evidence != "Nao informado"),
            "suggested_title": self.suggested_title,
            "ticket_to_complement_id": self.ticket_to_complement_id,
        }

