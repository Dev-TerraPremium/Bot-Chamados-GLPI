from app.local_light_ai.generative_title_generator import GenerativeTitleGenerator
from app.application_config.settings import AppSettings
from app.local_light_ai.generative_title_generator import build_generative_title_generator
from app.triage_rules.title_generation_service import TitleGenerationService


class FakeTitleClient:
    def __init__(self, title: str) -> None:
        self.title = title
        self.user_prompt = ""

    def generate_json(self, system_prompt: str, user_prompt: str, options: dict) -> dict:
        self.user_prompt = user_prompt
        return {"title": self.title}


def test_static_title_generator_does_not_prefix_category() -> None:
    title = TitleGenerationService().generate_title(
        "INFRAESTRUTURA > PERIFERICOS > MOUSE/TECLADO",
        "Solicito a compra de um kit mouse e teclado.",
    )

    assert title == "Solicito a compra de um kit mouse e teclado"
    assert "INFRAESTRUTURA" not in title


def test_generative_title_generator_strips_category_prefix_from_model_output() -> None:
    client = FakeTitleClient(
        "INFRAESTRUTURA > PERIFERICOS > MOUSE/TECLADO - Mouse com falha no clique"
    )
    generator = GenerativeTitleGenerator(client=client)

    title = generator.generate_title(
        "INFRAESTRUTURA > PERIFERICOS > MOUSE/TECLADO",
        "Usuario informa falha no clique do mouse.",
    )

    assert title == "Mouse com falha no clique"
    assert "INFRAESTRUTURA" not in title
    assert "Categoria" not in client.user_prompt


def test_title_builder_is_deterministic_by_default(monkeypatch) -> None:
    fake_client = FakeTitleClient("Titulo de IA que nao deve ser chamado")

    monkeypatch.setattr(
        "app.local_light_ai.generative_title_generator.build_local_generative_client",
        lambda settings: (fake_client, "google:gemini-3.1-flash-lite"),
    )

    generator = build_generative_title_generator(
        AppSettings(local_light_ai_mode="generative_google")
    )

    title = generator.generate_title(
        "SISTEMAS > SOLUTION > SUPORTE",
        "Estou com problema de nota na tela 1234.",
    )

    assert title == "Estou com problema de nota na tela 1234"
    assert fake_client.user_prompt == ""
