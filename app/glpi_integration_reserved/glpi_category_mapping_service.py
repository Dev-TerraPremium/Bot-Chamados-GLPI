from app.triage_rules.category_catalog import get_category_by_id


class GLPICategoryMappingService:
    """Maps internal bot categories to future GLPI category IDs."""

    def map_internal_category_to_glpi(self, internal_category_id: int) -> dict:
        category = get_category_by_id(internal_category_id)
        if category is None:
            return {
                "internal_category_id": 12,
                "internal_category_name": "Outro",
                "glpi_category_id": 12,
            }
        return {
            "internal_category_id": category.id,
            "internal_category_name": category.name,
            "glpi_category_id": category.id,
        }

