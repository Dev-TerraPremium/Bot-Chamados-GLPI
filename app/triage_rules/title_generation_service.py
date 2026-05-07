import re


class TitleGenerationService:
    def generate_title(self, category_name: str, description: str) -> str:
        normalized_description = re.sub(r"\s+", " ", description).strip()
        normalized_description = normalized_description.rstrip(".!?")
        if not normalized_description:
            return "Chamado de TI"

        short_description = normalized_description[:70].strip()
        return short_description[:100]
