import re

from app.application_config.settings import AppSettings
from app.local_light_ai.generative_description_organizer import (
    LocalGenerativeClient,
    build_local_generative_client,
)
from app.triage_rules.title_generation_service import TitleGenerationService


class GenerativeTitleGenerator:
    def __init__(self, client: LocalGenerativeClient, num_predict: int = 150):
        self.client = client
        self.num_predict = num_predict

    def generate_title(self, category_name: str, description: str) -> str:
        if not description.strip():
            return "Chamado de TI"

        system_prompt = (
            "Voce e um gerador de titulos curtos para chamados de TI.\n"
            "Crie um titulo natural, direto e com no maximo 10 palavras.\n"
            "O titulo deve resumir objeto + sintoma, sem copiar a frase inteira.\n"
            "Nao inclua categoria, caminho de categoria, setor interno, solicitante "
            "ou metadados.\n"
            "Exemplos bons: Computador com barulho excessivo; Mouse com falha no clique.\n"
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
                return self._clean_title(title, category_name)
        except Exception:
            pass

        return TitleGenerationService().generate_title(category_name, description)

    @staticmethod
    def _clean_title(title: str, category_name: str) -> str:
        return TitleGenerationService.clean_title(
            re.sub(r"\s+", " ", title),
            category_name,
        )


def build_generative_title_generator(
    settings: AppSettings,
) -> GenerativeTitleGenerator | TitleGenerationService:
    if not settings.ai_generative_title_enabled:
        return TitleGenerationService()

    client, _ = build_local_generative_client(settings)
    return GenerativeTitleGenerator(client=client, num_predict=150)
