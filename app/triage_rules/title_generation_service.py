import re


class TitleGenerationService:
    def generate_title(self, category_name: str, description: str) -> str:
        normalized_description = re.sub(r"\s+", " ", description).strip()
        normalized_description = normalized_description.rstrip(".!?")
        if not normalized_description:
            return category_name

        short_description = normalized_description[:70].strip()
        title = f"{category_name} - {short_description}"
        return title[:100]

