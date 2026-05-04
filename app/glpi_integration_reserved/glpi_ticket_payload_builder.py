from app.ticket_domain.ticket_models import TicketDraft


class GLPITicketPayloadBuilder:
    """Builds the isolated payload that will later be adapted to GLPI REST."""

    def build_from_ticket_draft(self, draft: TicketDraft) -> dict:
        return {
            "requester_name": draft.requester_name,
            "requester_login": draft.requester_login,
            "requester_email": draft.requester_email,
            "glpi_user_id": draft.glpi_user_id,
            "channel": draft.channel,
            "opening_mode": draft.opening_mode,
            "category_id": draft.category_id,
            "category_name": draft.category_name,
            "title": draft.title,
            "description": draft.description,
            "impact_id": draft.impact_id,
            "impact_label": draft.impact_label,
            "severity": draft.severity,
            "location": draft.location,
            "evidence": draft.evidence,
            "future_glpi_input": {
                "name": draft.title,
                "content": draft.description,
                "urgency": draft.impact_id,
                "impact": draft.impact_id,
                "priority": draft.severity,
                "itilcategories_id": draft.category_id,
                "_users_id_requester": draft.glpi_user_id,
            },
        }

