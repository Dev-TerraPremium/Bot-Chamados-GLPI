import logging

from app.application_config.settings import AppSettings
from app.local_light_ai.generative_description_organizer import (
    LocalGenerativeClient,
    build_local_generative_client,
)
from app.triage_rules.title_generation_service import TitleGenerationService


logger = logging.getLogger(__name__)


class GenerativeTitleGenerator:
    def __init__(self, client: LocalGenerativeClient, num_predict: int = 150):
        self.client = client
        self.num_predict = num_predict
        self.fallback_service = TitleGenerationService()

    def generate_title(self, category_name: str, description: str) -> str:
        if not description.strip():
            return TitleGenerationService.FALLBACK_TITLE

        system_prompt = (
            "Voce e um gerador de titulos curtos para chamados de TI.\n"
            "Crie um titulo natural, direto, profissional e com no maximo 10 palavras.\n"
            "Nao inclua categoria, caminho de categoria, setor interno, solicitante "
            "ou metadados.\n"
            "Nao corte palavras e nao use reticencias.\n"
            "Exemplo bom: Mouse com falha no clique.\n"
            "Retorne estritamente em JSON com a chave 'title'."
        )
        user_prompt = (
            f"Descricao: {description}\n\n"
            'Retorne JSON no formato: {"title": "Seu titulo aqui"}'
        )

        try:
            payload = self.client.generate_json(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                options={
                    "temperature": 0.2,
                    "num_predict": self.num_predict,
                    "purpose": "titulo_chamado",
                },
            )
            title = str(payload.get("title", "")).strip()
            if title:
                return TitleGenerationService.clean_title(title, category_name)
        except Exception as exc:
            logger.warning(
                "generative_title_generation_failed",
                extra={"error": str(exc)},
            )

        return self.fallback_service.generate_title(category_name, description)


def build_generative_title_generator(
    settings: AppSettings,
) -> GenerativeTitleGenerator | TitleGenerationService:
    if not settings.ai_generative_title_enabled:
        return TitleGenerationService()

    client, _ = build_local_generative_client(settings)
    return GenerativeTitleGenerator(client=client, num_predict=150)
