import json
from app.local_light_ai.generative_description_organizer import LocalGenerativeClient, MockLocalGenerativeClient, OllamaLocalGenerativeClient
from app.application_config.settings import AppSettings

class GenerativeTitleGenerator:
    def __init__(self, client: LocalGenerativeClient, num_predict: int = 150):
        self.client = client
        self.num_predict = num_predict

    def generate_title(self, category_name: str, description: str) -> str:
        if not description.strip():
            return category_name
            
        system_prompt = (
            "Você é um gerador de títulos curtos para chamados de TI.\n"
            "Crie um título que resuma o problema em no máximo 10 palavras.\n"
            "Retorne estritamente em JSON com a chave 'title'."
        )
        user_prompt = f"Categoria: {category_name}\nDescrição: {description}\n\nRetorne JSON no formato: {{\"title\": \"Seu titulo aqui\"}}"
        
        try:
            payload = self.client.generate_json(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                options={
                    "temperature": 0.2,
                    "num_predict": self.num_predict,
                }
            )
            title = str(payload.get("title", "")).strip()
            if title:
                return f"{category_name} - {title}"[:100]
        except Exception:
            pass

        return f"{category_name} - {description[:70].strip()}"[:100]

def build_generative_title_generator(settings: AppSettings) -> GenerativeTitleGenerator:
    if settings.local_light_ai_mode.casefold() == "mock":
        client = MockLocalGenerativeClient()
    else:
        client = OllamaLocalGenerativeClient(
            base_url=settings.ollama_base_url,
            model=settings.local_generative_model,
            timeout_seconds=settings.local_generative_timeout_seconds,
        )
    return GenerativeTitleGenerator(client=client, num_predict=150)
