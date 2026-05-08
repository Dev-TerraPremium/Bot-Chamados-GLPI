import json
from app.triage_rules.category_catalog import CATEGORY_OPTIONS
from app.triage_rules.category_matching_service import (
    CategoryMatch,
    CategoryMatchingService,
)
from app.local_light_ai.generative_description_organizer import (
    LocalGenerativeClient,
    build_local_generative_client,
)
from app.application_config.settings import AppSettings

class GenerativeCategorySuggester:
    def __init__(self, client: LocalGenerativeClient, num_predict: int = 250):
        self.client = client
        self.num_predict = num_predict

    def find_best_match(self, text: str) -> CategoryMatch:
        heuristic_match = CategoryMatchingService().find_best_match(text)
        if heuristic_match.confidence > 0:
            return heuristic_match

        categories_text = "\n".join(f"- {c.id}: {c.name} (ex: {', '.join(c.examples)})" for c in CATEGORY_OPTIONS)
        system_prompt = (
            "Você é um classificador de categorias de TI.\n"
            "Analise a descrição do problema e escolha o ID da categoria mais adequada.\n"
            "Nao explique o raciocinio e nao invente categorias.\n\n"
            "Categorias disponíveis:\n"
            f"{categories_text}\n\n"
            "Retorne APENAS um objeto JSON com 'category_id' (inteiro)."
        )
        user_prompt = f"Descrição do usuário: {text}\n\nRetorne JSON."
        
        try:
            payload = self.client.generate_json(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                options={
                    "temperature": 0.1,
                    "num_predict": self.num_predict,
                    "purpose": "categoria_chamado",
                }
            )
            cat_id = int(payload.get("category_id", 12))
        except Exception:
            return CategoryMatchingService().find_best_match(text)

        category_name = next((c.name for c in CATEGORY_OPTIONS if c.id == cat_id), "Outro")
        if category_name == "Outro":
            return CategoryMatchingService().find_best_match(text)
        
        return CategoryMatch(
            category_id=cat_id,
            category_name=category_name,
            confidence=0.9,
            matched_keyword="ai_inferred"
        )

def build_generative_category_suggester(settings: AppSettings) -> GenerativeCategorySuggester:
    client, _ = build_local_generative_client(settings)
    return GenerativeCategorySuggester(client=client, num_predict=300)
