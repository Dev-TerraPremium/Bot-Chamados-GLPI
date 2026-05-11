from typing import Any

from app.authentication_and_identity.authenticated_user_model import AuthenticatedUser
from app.conversation_engine.conversation_context import ConversationContext
from app.conversation_engine.conversation_states import ConversationState


class ConversationContextCodec:
    @staticmethod
    def to_dict(context: ConversationContext) -> dict[str, Any]:
        return {
            "session_id": context.session_id,
            "channel": context.channel,
            "user": context.user.to_safe_dict(),
            "state": context.state.value,
            "opening_mode": context.opening_mode,
            "ticket_type": context.ticket_type,
            "attachments": context.attachments,
            "selected_category_id": context.selected_category_id,
            "selected_category_name": context.selected_category_name,
            "selected_glpi_category_id": context.selected_glpi_category_id,
            "selected_category_complete_name": context.selected_category_complete_name,
            "pending_category_suggestion_id": context.pending_category_suggestion_id,
            "pending_category_suggestion_name": context.pending_category_suggestion_name,
            "pending_glpi_category_id": context.pending_glpi_category_id,
            "pending_category_complete_name": context.pending_category_complete_name,
            "category_selection_options": context.category_selection_options,
            "original_description": context.original_description,
            "organized_description": context.organized_description,
            "description_clarification_question": (
                context.description_clarification_question
            ),
            "description_clarification_turns": context.description_clarification_turns,
            "impact_id": context.impact_id,
            "impact_label": context.impact_label,
            "severity": context.severity,
            "location": context.location,
            "glpi_location_id": context.glpi_location_id,
            "location_selection_options": context.location_selection_options,
            "awaiting_location_retry": context.awaiting_location_retry,
            "evidence": context.evidence,
            "suggested_title": context.suggested_title,
            "ticket_preview": context.ticket_preview,
            "ticket_to_complement_id": context.ticket_to_complement_id,
            "complement_original_text": context.complement_original_text,
            "complement_rewritten_text": context.complement_rewritten_text,
        }

    @staticmethod
    def from_dict(data: dict[str, Any]) -> ConversationContext:
        user_data = data["user"]
        return ConversationContext(
            session_id=str(data["session_id"]),
            channel=str(data["channel"]),
            user=AuthenticatedUser(
                full_name=str(user_data["full_name"]),
                login=str(user_data["login"]),
                email=str(user_data["email"]),
                glpi_user_id=int(user_data["glpi_user_id"]),
            ),
            state=ConversationState(str(data["state"])),
            opening_mode=data.get("opening_mode"),
            ticket_type=int(data.get("ticket_type") or 1),
            attachments=[
                {
                    "file_name": str(item.get("file_name", "")),
                    "mime_type": str(item.get("mime_type", "application/octet-stream")),
                    "data_base64": str(item.get("data_base64", "")),
                }
                for item in data.get("attachments", [])
                if isinstance(item, dict)
            ],
            selected_category_id=data.get("selected_category_id"),
            selected_category_name=data.get("selected_category_name"),
            selected_glpi_category_id=data.get("selected_glpi_category_id"),
            selected_category_complete_name=data.get("selected_category_complete_name"),
            pending_category_suggestion_id=data.get("pending_category_suggestion_id"),
            pending_category_suggestion_name=data.get("pending_category_suggestion_name"),
            pending_glpi_category_id=data.get("pending_glpi_category_id"),
            pending_category_complete_name=data.get("pending_category_complete_name"),
            category_selection_options=[
                item
                for item in data.get("category_selection_options", [])
                if isinstance(item, dict)
            ],
            original_description=data.get("original_description"),
            organized_description=data.get("organized_description"),
            description_clarification_question=data.get(
                "description_clarification_question"
            ),
            description_clarification_turns=[
                {
                    "question": str(turn.get("question", "")),
                    "answer": str(turn.get("answer", "")),
                }
                for turn in data.get("description_clarification_turns", [])
                if isinstance(turn, dict)
            ],
            impact_id=data.get("impact_id"),
            impact_label=data.get("impact_label"),
            severity=data.get("severity"),
            location=data.get("location"),
            glpi_location_id=data.get("glpi_location_id"),
            location_selection_options=[
                item
                for item in data.get("location_selection_options", [])
                if isinstance(item, dict)
            ],
            awaiting_location_retry=bool(data.get("awaiting_location_retry")),
            evidence=data.get("evidence"),
            suggested_title=data.get("suggested_title"),
            ticket_preview=data.get("ticket_preview"),
            ticket_to_complement_id=data.get("ticket_to_complement_id"),
            complement_original_text=data.get("complement_original_text"),
            complement_rewritten_text=data.get("complement_rewritten_text"),
        )
