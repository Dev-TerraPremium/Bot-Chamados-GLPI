import pytest

from app.application_config.settings import AppSettings
from app.glpi_integration_reserved.glpi_category_catalog_service import GLPICategoryOption
from app.local_light_ai.description_organization_models import (
    LocalGenerativeAIUnavailableError,
)
from app.local_light_ai.generative_description_organizer import (
    build_local_generative_client,
)
from app.local_light_ai.generative_title_generator import (
    build_generative_title_generator,
)
from app.triage_rules.glpi_category_suggestion_service import (
    build_glpi_category_suggestion_service,
)


class FakeClient:
    def __init__(self, payload: dict) -> None:
        self.payload = payload
        self.calls: list[dict] = []

    def generate_json(self, system_prompt: str, user_prompt: str, options: dict) -> dict:
        self.calls.append(
            {
                "system_prompt": system_prompt,
                "user_prompt": user_prompt,
                "options": options,
            }
        )
        return self.payload


class FakeCatalog:
    def __init__(self) -> None:
        self.category = GLPICategoryOption(
            id=544,
            name="WI-FI",
            complete_name="INFRAESTRUTURA > REDES > WI-FI",
            entity_id=3,
            parent_id=528,
            level=3,
        )

    def get_categories(self, ticket_type=None):
        return [self.category]

    def get_by_id(self, category_id: int):
        return self.category if category_id == 544 else None

    def search(self, query: str, *, ticket_type=None, limit: int = 5):
        return [self.category]


class NoSearchMatchCatalog(FakeCatalog):
    def search(self, query: str, *, ticket_type=None, limit: int = 5):
        return []


def test_disabled_ollama_mode_fails_fast() -> None:
    settings = AppSettings(
        local_light_ai_mode="generative_ollama",
        local_ollama_enabled=False,
    )

    with pytest.raises(LocalGenerativeAIUnavailableError):
        build_local_generative_client(settings)


def test_glpi_category_suggester_uses_text_search_before_ai(monkeypatch) -> None:
    fake_client = FakeClient({"category_id": 544})

    monkeypatch.setattr(
        "app.triage_rules.glpi_category_suggestion_service.build_local_generative_client",
        lambda settings: (fake_client, "google:gemini-2.5-flash-lite"),
    )

    service = build_glpi_category_suggestion_service(
        AppSettings(
            glpi_integration_mode="real",
            local_light_ai_mode="generative_google",
            local_ollama_enabled=False,
        ),
        FakeCatalog(),
    )
    match = service.find_best_match("wifi caindo no deposito", ticket_type=1)

    assert match.category_id == 544
    assert match.category_name == "INFRAESTRUTURA > REDES > WI-FI"
    assert match.matched_keyword == "text_search"
    assert not fake_client.calls


def test_glpi_category_suggester_uses_ai_when_text_search_has_no_match(monkeypatch) -> None:
    fake_client = FakeClient({"category_id": 544})

    monkeypatch.setattr(
        "app.triage_rules.glpi_category_suggestion_service.build_local_generative_client",
        lambda settings: (fake_client, "google:gemini-2.5-flash-lite"),
    )

    service = build_glpi_category_suggestion_service(
        AppSettings(
            glpi_integration_mode="real",
            local_light_ai_mode="generative_google",
            local_ollama_enabled=False,
        ),
        NoSearchMatchCatalog(),
    )
    match = service.find_best_match("wifi caindo no deposito", ticket_type=1)

    assert match.category_id == 544
    assert match.matched_keyword == "ai_inferred"
    assert fake_client.calls


def test_title_generator_builder_uses_shared_ai_builder(monkeypatch) -> None:
    fake_client = FakeClient({"title": "Mouse com falha no clique"})

    monkeypatch.setattr(
        "app.local_light_ai.generative_title_generator.build_local_generative_client",
        lambda settings: (fake_client, "google:gemini-2.5-flash-lite"),
    )

    generator = build_generative_title_generator(
        AppSettings(
            local_light_ai_mode="generative_google",
            local_ollama_enabled=False,
            ai_generative_title_enabled=True,
        )
    )
    title = generator.generate_title(
        "INFRAESTRUTURA > PERIFERICOS > MOUSE/TECLADO",
        "O mouse esta falhando ao clicar.",
    )

    assert title == "Mouse com falha no clique"
    assert fake_client.calls
