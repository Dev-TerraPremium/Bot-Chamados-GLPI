import json

from app.application_config.settings import AppSettings
from app.glpi_integration_reserved.glpi_category_catalog_service import (
    GLPICategoryCatalogServiceInterface,
    GLPICategoryOption,
)
from app.local_light_ai.generative_description_organizer import (
    LocalGenerativeClient,
    MockLocalGenerativeClient,
    OllamaLocalGenerativeClient,
)
from app.triage_rules.category_matching_service import CategoryMatch


class GLPICategorySuggestionService:
    def __init__(
        self,
        catalog: GLPICategoryCatalogServiceInterface,
        client: LocalGenerativeClient,
        num_predict: int = 300,
    ) -> None:
        self.catalog = catalog
        self.client = client
        self.num_predict = num_predict

    def find_best_match(
        self,
        text: str,
        *,
        ticket_type: int | None = None,
    ) -> CategoryMatch:
        categories = self.catalog.get_categories(ticket_type)
        if not categories:
            return CategoryMatch(0, "Categoria GLPI indisponivel", 0.0, "")

        category_by_id = {category.id: category for category in categories}
        try:
            category_id = self._ask_model(text, categories)
            if category_id in category_by_id:
                category = category_by_id[category_id]
                return self._match(category, confidence=0.9, source="ai_inferred")
        except Exception:
            pass

        matches = self.catalog.search(text, ticket_type=ticket_type, limit=1)
        if matches:
            return self._match(matches[0], confidence=0.65, source="text_search")

        fallback = self._fallback_category(categories)
        return self._match(fallback, confidence=0.0, source="fallback")

    def _ask_model(self, text: str, categories: list[GLPICategoryOption]) -> int:
        categories_text = "\n".join(
            f"- {category.id}: {category.display_name}" for category in categories
        )
        payload = self.client.generate_json(
            system_prompt=(
                "Voce e um classificador de categorias GLPI de TI.\n"
                "Escolha exatamente um ID da lista abaixo para a descricao do usuario.\n"
                "Nao invente categorias.\n\n"
                f"Categorias disponiveis:\n{categories_text}\n\n"
                "Retorne apenas JSON: {\"category_id\": numero}."
            ),
            user_prompt=f"Descricao do usuario: {text}\n\nRetorne JSON.",
            options={"temperature": 0.1, "num_predict": self.num_predict},
        )
        if isinstance(payload, str):
            payload = json.loads(payload)
        return int(payload.get("category_id") or 0)

    @staticmethod
    def _match(
        category: GLPICategoryOption,
        *,
        confidence: float,
        source: str,
    ) -> CategoryMatch:
        return CategoryMatch(
            category_id=category.id,
            category_name=category.display_name,
            confidence=confidence,
            matched_keyword=source,
        )

    @staticmethod
    def _fallback_category(
        categories: list[GLPICategoryOption],
    ) -> GLPICategoryOption:
        return next(
            (category for category in categories if category.id == 659),
            categories[0],
        )


def build_glpi_category_suggestion_service(
    settings: AppSettings,
    catalog: GLPICategoryCatalogServiceInterface,
) -> GLPICategorySuggestionService:
    if settings.local_light_ai_mode.casefold() == "mock":
        client = MockLocalGenerativeClient()
    else:
        client = OllamaLocalGenerativeClient(
            base_url=settings.ollama_base_url,
            model=settings.local_generative_model,
            timeout_seconds=settings.local_generative_timeout_seconds,
        )
    return GLPICategorySuggestionService(
        catalog=catalog,
        client=client,
        num_predict=settings.ai_ollama_num_predict,
    )
