from app.glpi_integration_reserved.glpi_category_mapping_service import (
    GLPICategoryMappingService,
)
from app.ticket_domain.ticket_models import TicketDraft


class GLPITicketPayloadBuilder:
    """Builds the internal and GLPI REST payload for a ticket draft."""

    def __init__(
        self,
        category_mapping_service: GLPICategoryMappingService | None = None,
        default_entity_id: int = 0,
        default_requester_user_id: int = 0,
    ) -> None:
        self.category_mapping_service = (
            category_mapping_service or GLPICategoryMappingService()
        )
        self.default_entity_id = default_entity_id
        self.default_requester_user_id = default_requester_user_id

    def build_from_ticket_draft(self, draft: TicketDraft) -> dict:
        category_mapping = None
        if not draft.glpi_category_id:
            category_mapping = self.category_mapping_service.map_internal_category_to_glpi(
                draft.category_id
            )
        glpi_category_id = draft.glpi_category_id or category_mapping.glpi_category_id
        category_name = draft.glpi_category_complete_name or draft.category_name
        requester_user_id = (
            draft.glpi_user_id
            if draft.glpi_category_id
            else self.default_requester_user_id or draft.glpi_user_id
        )
        entity_id = self.default_entity_id
        content = self._build_glpi_content(draft)
        return {
            "requester_name": draft.requester_name,
            "requester_login": draft.requester_login,
            "requester_email": draft.requester_email,
            "glpi_user_id": requester_user_id,
            "channel": draft.channel,
            "opening_mode": draft.opening_mode,
            "category_id": draft.category_id,
            "category_name": category_name,
            "glpi_category_id": glpi_category_id,
            "title": draft.title,
            "description": draft.description,
            "impact_id": draft.impact_id,
            "impact_label": draft.impact_label,
            "severity": draft.severity,
            "location": draft.location,
            "evidence": draft.evidence,
            "attachments": draft.attachments,
            "glpi_input": {
                "name": draft.title,
                "content": content,
                "entities_id": entity_id,
                "itilcategories_id": glpi_category_id,
                "_users_id_requester": requester_user_id,
                "type": draft.ticket_type,
                "urgency": self._to_glpi_level(draft.impact_id),
                "impact": self._to_glpi_level(draft.impact_id),
                "priority": self._severity_to_priority(draft.severity),
                "status": 1,
            },
        }

    @staticmethod
    def _build_glpi_content(draft: TicketDraft) -> str:
        evidence = draft.evidence or "Não informado"
        attachment_note = "Nenhum anexo recebido."
        if draft.attachments:
            attachment_note = "Anexos recebidos: " + ", ".join(
                str(item.get("file_name") or "anexo") for item in draft.attachments
            )
        return (
            f"Descrição organizada:\n{draft.description}\n\n"
            f"Impacto informado:\n{draft.impact_label}\n\n"
            f"Gravidade calculada:\n{draft.severity}\n\n"
            f"Localidade/Setor:\n{draft.location}\n\n"
            f"Evidência/Informação adicional:\n{evidence}\n\n"
            f"{attachment_note}\n\n"
            f"Canal de origem:\n{draft.channel}\n"
            f"Solicitante informado pelo assistente:\n"
            f"{draft.requester_name} ({draft.requester_login})"
        )

    @staticmethod
    def _to_glpi_level(impact_id: int) -> int:
        return max(1, min(int(impact_id), 5))

    @staticmethod
    def _severity_to_priority(severity: str) -> int:
        normalized = severity.casefold()
        if normalized == "baixa":
            return 2
        if normalized == "média" or normalized == "media":
            return 3
        if normalized == "alta":
            return 4
        if normalized == "crítica" or normalized == "critica":
            return 5
        return 3
