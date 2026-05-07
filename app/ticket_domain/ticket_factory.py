from app.ticket_domain.ticket_models import TicketDraft
from app.ticket_domain.ticket_validation_service import TicketValidationService


class TicketFactory:
    def __init__(self, validation_service: TicketValidationService | None = None) -> None:
        self.validation_service = validation_service or TicketValidationService()

    def create_draft_from_context(self, context) -> TicketDraft:
        draft = TicketDraft(
            requester_name=context.user.full_name,
            requester_login=context.user.login,
            requester_email=context.user.email,
            glpi_user_id=context.user.glpi_user_id,
            channel=context.channel,
            opening_mode=context.opening_mode or "",
            category_id=context.selected_category_id or 0,
            category_name=context.selected_category_name or "",
            glpi_category_id=context.selected_glpi_category_id or 0,
            glpi_category_complete_name=context.selected_category_complete_name or "",
            description=context.organized_description or context.original_description or "",
            impact_id=context.impact_id or 0,
            impact_label=context.impact_label or "",
            severity=context.severity or "",
            location=context.location or "",
            evidence=context.evidence or "Não informado",
            title=context.suggested_title or "",
            ticket_type=context.ticket_type,
            attachments=context.attachments.copy() if context.attachments else [],
        )
        self.validation_service.validate_draft(draft)
        return draft
