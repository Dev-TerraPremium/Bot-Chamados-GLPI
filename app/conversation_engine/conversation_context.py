from dataclasses import dataclass, field
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
    ticket_type: int = 1
    attachments: list[dict[str, Any]] = field(default_factory=list)
    selected_category_id: int | None = None
    selected_category_name: str | None = None
    selected_glpi_category_id: int | None = None
    selected_category_complete_name: str | None = None
    pending_category_suggestion_id: int | None = None
    pending_category_suggestion_name: str | None = None
    pending_glpi_category_id: int | None = None
    pending_category_complete_name: str | None = None
    category_selection_options: list[dict[str, Any]] = field(default_factory=list)
    original_description: str | None = None
    organized_description: str | None = None
    description_clarification_question: str | None = None
    description_clarification_turns: list[dict[str, str]] = field(default_factory=list)
    impact_id: int | None = None
    impact_label: str | None = None
    severity: str | None = None
    location: str | None = None
    glpi_location_id: int | None = None
    location_selection_options: list[dict[str, Any]] = field(default_factory=list)
    awaiting_location_retry: bool = False
    evidence: str | None = None
    suggested_title: str | None = None
    ticket_preview: dict[str, Any] | None = None
    ticket_to_complement_id: int | None = None
    complement_original_text: str | None = None
    complement_rewritten_text: str | None = None

    def reset_ticket_draft(self) -> None:
        self.opening_mode = None
        self.ticket_type = 1
        self.attachments = []
        self.selected_category_id = None
        self.selected_category_name = None
        self.selected_glpi_category_id = None
        self.selected_category_complete_name = None
        self.pending_category_suggestion_id = None
        self.pending_category_suggestion_name = None
        self.pending_glpi_category_id = None
        self.pending_category_complete_name = None
        self.category_selection_options = []
        self.original_description = None
        self.organized_description = None
        self.reset_description_clarification()
        self.impact_id = None
        self.impact_label = None
        self.severity = None
        self.location = None
        self.glpi_location_id = None
        self.location_selection_options = []
        self.awaiting_location_retry = False
        self.evidence = None
        self.suggested_title = None
        self.ticket_preview = None
        self.reset_complement()

    def reset_complement(self) -> None:
        self.ticket_to_complement_id = None
        self.complement_original_text = None
        self.complement_rewritten_text = None

    def reset_description_clarification(self) -> None:
        self.description_clarification_question = None
        self.description_clarification_turns.clear()

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
            "selected_glpi_category_id": self.selected_glpi_category_id,
            "selected_category_complete_name": self.selected_category_complete_name,
            "description_clarification_count": len(
                self.description_clarification_turns
            ),
            "impact_id": self.impact_id,
            "impact_label": self.impact_label,
            "severity": self.severity,
            "location": self.location,
            "glpi_location_id": self.glpi_location_id,
            "evidence_informed": bool(self.evidence and self.evidence != "Não informado"),
            "suggested_title": self.suggested_title,
            "ticket_to_complement_id": self.ticket_to_complement_id,
        }
