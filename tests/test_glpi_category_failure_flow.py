from uuid import uuid4

from app.application_config.settings import AppSettings
from app.conversation_engine.conversation_flow_controller import (
    ConversationFlowController,
)
from app.glpi_integration_reserved.glpi_future_real_client import GLPIClientError
from app.local_light_ai.description_organization_models import (
    DescriptionOrganizationResult,
)
from app.ticket_domain.ticket_models import TicketCreated


class FakeDescriptionOrganizer:
    def organize_ticket_description(
        self,
        user_text: str,
        category_name: str | None = None,
        purpose: str = "descricao_chamado",
    ) -> DescriptionOrganizationResult:
        return DescriptionOrganizationResult(
            status="organized",
            organized_text="Wi-Fi caindo no deposito.",
            clarification_question="",
            confidence=0.9,
            backend="fake-generative",
        )


class FailingRealCatalog:
    def get_categories(self, ticket_type=None):
        raise GLPIClientError("GLPI recusou a operacao solicitada.")

    def get_by_id(self, category_id: int):
        raise GLPIClientError("GLPI recusou a operacao solicitada.")

    def search(self, query: str, *, ticket_type=None, limit: int = 5):
        raise GLPIClientError("GLPI recusou a operacao solicitada.")


class FailingRealCategorySuggester:
    def find_best_match(self, text: str, *, ticket_type=None):
        raise GLPIClientError("GLPI recusou a operacao solicitada.")


class FakeUsageTracker:
    def increment(self, category_id: int) -> None:
        return None

    def top_categories(self, catalog, *, ticket_type=None, limit: int = 5):
        return catalog.get_categories(ticket_type)[:limit]


class FakeRealGLPIClient:
    def create_ticket(self, ticket_data: dict) -> TicketCreated:
        return TicketCreated(
            ticket_number=1234,
            title=ticket_data["title"],
            status="Aberto",
            severity=ticket_data["severity"],
            description=ticket_data["description"],
            category_name=ticket_data["category_name"],
            requester_login=ticket_data["requester_login"],
            glpi_user_id=ticket_data["glpi_user_id"],
            channel=ticket_data["channel"],
            location=ticket_data["location"],
            impact_label=ticket_data["impact_label"],
            evidence=ticket_data["evidence"],
            opening_mode=ticket_data["opening_mode"],
            created_at="2026-05-07T00:00:00Z",
        )


def send(controller: ConversationFlowController, session_id: str, message: str) -> dict:
    result = controller.process_message(
        session_id=session_id,
        message=message,
    )
    return {
        "session_id": result.session_id,
        "bot_message": result.bot_message,
        "state": result.state,
    }


def test_real_open_ticket_flow_does_not_raise_500_when_glpi_category_lookup_fails() -> None:
    session_id = str(uuid4())
    controller = ConversationFlowController(
        settings=AppSettings(
            glpi_integration_mode="real",
            glpi_base_url="https://glpi.local/apirest.php",
            glpi_app_token="app",
            glpi_user_token="user",
            glpi_default_entity_id=3,
            glpi_default_profile_id=4,
            state_backend="memory",
            use_celery_workers=False,
            ai_guided_detailing_enabled=False,
        ),
        description_organizer=FakeDescriptionOrganizer(),
        glpi_client=FakeRealGLPIClient(),
    )
    controller.category_catalog = FailingRealCatalog()
    controller.category_matching_service = FailingRealCategorySuggester()
    controller.category_usage_tracker = FakeUsageTracker()

    send(controller, session_id, "__start__")
    send(controller, session_id, "1")
    send(controller, session_id, "1")
    response = send(controller, session_id, "wifi caindo no deposito")

    assert response["state"] == "category_selection"
    assert "não consegui consultar as categorias reais do glpi agora" in response["bot_message"].lower()
    assert "não vou perder sua descrição" in response["bot_message"].lower()
