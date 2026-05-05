import os
from dataclasses import dataclass

from app.triage_rules.category_catalog import get_category_by_id


@dataclass(frozen=True, slots=True)
class GLPICategoryMapping:
    internal_category_id: int
    internal_category_name: str
    glpi_category_id: int


DEFAULT_GLPI_CATEGORY_IDS: dict[int, int] = {
    1: 535,
    2: 455,
    3: 490,
    4: 622,
    5: 487,
    6: 416,
    7: 587,
    8: 647,
    9: 639,
    10: 445,
    11: 544,
    12: 659,
}

ENV_NAMES_BY_INTERNAL_CATEGORY: dict[int, str] = {
    1: "GLPI_CATEGORY_INTERNET_REDE_ID",
    2: "GLPI_CATEGORY_COMPUTADOR_NOTEBOOK_ID",
    3: "GLPI_CATEGORY_IMPRESSORA_ID",
    4: "GLPI_CATEGORY_SISTEMA_ERP_ID",
    5: "GLPI_CATEGORY_EMAIL_MICROSOFT_365_ID",
    6: "GLPI_CATEGORY_ACESSO_SENHA_ID",
    7: "GLPI_CATEGORY_TELEFONIA_ID",
    8: "GLPI_CATEGORY_GLPI_ID",
    9: "GLPI_CATEGORY_SOLICITACAO_EQUIPAMENTO_ID",
    10: "GLPI_CATEGORY_CAMERAS_CFTV_ID",
    11: "GLPI_CATEGORY_UBIQUITI_WIFI_ID",
    12: "GLPI_CATEGORY_OUTRO_ID",
}


class GLPICategoryMappingService:
    """Maps internal bot categories to GLPI ITIL category IDs."""

    def map_internal_category_to_glpi(
        self, internal_category_id: int
    ) -> GLPICategoryMapping:
        category = get_category_by_id(internal_category_id) or get_category_by_id(12)
        glpi_category_id = self._configured_glpi_category_id(category.id)
        return GLPICategoryMapping(
            internal_category_id=category.id,
            internal_category_name=category.name,
            glpi_category_id=glpi_category_id,
        )

    def as_dict(self, internal_category_id: int) -> dict:
        mapping = self.map_internal_category_to_glpi(internal_category_id)
        return {
            "internal_category_id": mapping.internal_category_id,
            "internal_category_name": mapping.internal_category_name,
            "glpi_category_id": mapping.glpi_category_id,
        }

    @staticmethod
    def _configured_glpi_category_id(internal_category_id: int) -> int:
        env_name = ENV_NAMES_BY_INTERNAL_CATEGORY[internal_category_id]
        raw_value = os.getenv(env_name)
        if raw_value:
            return int(raw_value)
        return DEFAULT_GLPI_CATEGORY_IDS[internal_category_id]
