from app.ticket_domain.ticket_models import TicketDraft


class TicketValidationService:
    REQUIRED_FIELDS = (
        "requester_login",
        "glpi_user_id",
        "channel",
        "opening_mode",
        "category_id",
        "category_name",
        "description",
        "impact_id",
        "impact_label",
        "severity",
        "location",
        "title",
    )

    def validate_draft(self, draft: TicketDraft) -> None:
        missing_fields = [
            field_name
            for field_name in self.REQUIRED_FIELDS
            if not getattr(draft, field_name)
        ]
        if missing_fields:
            raise ValueError(
                "Campos obrigatorios ausentes no chamado: "
                + ", ".join(missing_fields)
            )

