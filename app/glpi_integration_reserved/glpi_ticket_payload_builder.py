import unicodedata

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
        require_glpi_category: bool = False,
    ) -> None:
        self.category_mapping_service = (
            category_mapping_service or GLPICategoryMappingService()
        )
        self.default_entity_id = default_entity_id
        self.default_requester_user_id = default_requester_user_id
        self.require_glpi_category = require_glpi_category

    def build_from_ticket_draft(self, draft: TicketDraft) -> dict:
        if self.require_glpi_category and not draft.glpi_category_id:
            raise ValueError("Categoria GLPI real obrigatoria para abertura em producao.")
        if self.require_glpi_category and not draft.glpi_location_id:
            raise ValueError("Localidade GLPI obrigatoria para abertura em producao.")

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
            "glpi_location_id": draft.glpi_location_id,
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
                "locations_id": draft.glpi_location_id,
                "status": 1,
            },
        }

    @staticmethod
    def _build_glpi_content(draft: TicketDraft) -> str:
        sections = [draft.description.strip()]

        evidence = (draft.evidence or "").strip()
        if evidence and _normalize_control_text(evidence) != "nao informado":
            sections.append(f"Informacao adicional: {evidence}")

        if draft.attachments:
            sections.append(
                "Anexos recebidos: "
                + ", ".join(
                    str(item.get("file_name") or "anexo")
                    for item in draft.attachments
                )
            )

        return "\n\n".join(section for section in sections if section)

    @staticmethod
    def _to_glpi_level(impact_id: int) -> int:
        return max(1, min(int(impact_id), 5))

    @staticmethod
    def _severity_to_priority(severity: str) -> int:
        normalized = _normalize_control_text(severity)
        if normalized == "baixa":
            return 2
        if normalized == "media":
            return 3
        if normalized == "alta":
            return 4
        if normalized == "critica":
            return 5
        return 3


def _normalize_control_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value.casefold())
    return "".join(char for char in normalized if not unicodedata.combining(char)).strip()
