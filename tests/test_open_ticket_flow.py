from uuid import uuid4

from app.application_config.settings import AppSettings
from app.background_jobs.tasks import (
    create_glpi_ticket_task,
    organize_description_task,
    worker_ticket_store,
)
from app.conversation_engine.conversation_flow_controller import (
    ConversationFlowController,
)
from app.local_light_ai.description_organization_models import (
    DescriptionOrganizationResult,
)


class FakeDescriptionOrganizer:
    def __init__(self, organized_text: str) -> None:
        self.organized_text = organized_text

    def organize_ticket_description(
        self,
        user_text: str,
        category_name: str | None = None,
        purpose: str = "descricao_chamado",
    ) -> DescriptionOrganizationResult:
        return DescriptionOrganizationResult(
            status="organized",
            organized_text=self.organized_text,
            clarification_question="",
            confidence=0.9,
            backend="fake-generative",
        )


def send(controller: ConversationFlowController, session_id: str, message: str) -> dict:
    result = controller.process_message(session_id=session_id, message=message)
    return {
        "session_id": result.session_id,
        "bot_message": result.bot_message,
        "state": result.state,
        "ticket_preview": result.ticket_preview,
        "created_ticket": result.created_ticket,
    }


def test_open_ticket_flow_uses_automatic_category_assignment() -> None:
    session_id = str(uuid4())
    controller = ConversationFlowController(
        settings=AppSettings(ai_guided_detailing_enabled=False),
        description_organizer=FakeDescriptionOrganizer("Wi-Fi caindo no depósito.")
    )

    send(controller, session_id, "__start__")
    open_prompt = send(controller, session_id, "1")
    assert "abrir seu chamado" in open_prompt["bot_message"]

    category_response = send(controller, session_id, "wifi caindo no deposito")
    assert category_response["state"] == "category_assignment_confirmation"
    assert "Ubiquiti / Wi-Fi" in category_response["bot_message"]

    send(controller, session_id, "1")
    send(controller, session_id, "1")
    send(controller, session_id, "2")
    send(controller, session_id, "TI - Matriz")
    summary_response = send(controller, session_id, "2")
    assert summary_response["ticket_preview"]["category"] == "Ubiquiti / Wi-Fi"

    created_response = send(controller, session_id, "1")
    assert "Chamado simulado criado com sucesso" in created_response["bot_message"]
    assert created_response["created_ticket"]["status"] == "Aberto"
    assert created_response["created_ticket"]["category_name"] == "Ubiquiti / Wi-Fi"


def test_open_ticket_flow_allows_manual_category_assignment() -> None:
    session_id = str(uuid4())
    controller = ConversationFlowController(
        settings=AppSettings(ai_guided_detailing_enabled=False),
        description_organizer=FakeDescriptionOrganizer(
            "Estou com meu acesso à pasta RH bloqueado."
        )
    )

    send(controller, session_id, "__start__")
    send(controller, session_id, "1")
    send(controller, session_id, "Estou com meu acesso a pasta RH bloqueado")
    manual_response = send(controller, session_id, "2")
    assert "Escolha a categoria manualmente" in manual_response["bot_message"]

    review_response = send(controller, session_id, "6")
    assert "acesso à pasta RH bloqueado" in review_response["bot_message"]

    send(controller, session_id, "1")
    send(controller, session_id, "3")
    send(controller, session_id, "RH - Rondonópolis")
    summary_response = send(controller, session_id, "2")

    assert summary_response["state"] == "final_confirmation"
    assert summary_response["ticket_preview"]["severity"] == "Alta"
    assert summary_response["ticket_preview"]["category"] == "Acesso / Senha"

    created_response = send(controller, session_id, "1")
    assert created_response["created_ticket"]["severity"] == "Alta"
    assert created_response["created_ticket"]["glpi_user_id"] == 1001


def test_open_ticket_flow_uses_celery_glpi_client_in_mock_mode(monkeypatch) -> None:
    class FakeDescriptionAsyncResult:
        def get(self, timeout: int, disable_sync_subtasks: bool):
            return {
                "status": "organized",
                "organized_text": "Wifi caindo no deposito.",
                "clarification_question": "",
                "confidence": 0.99,
                "backend": "mock-local-ai",
            }

    class FakeTicketAsyncResult:
        def get(self, timeout: int, disable_sync_subtasks: bool):
            return {
                "ticket_number": 10001,
                "title": "Wi-Fi",
                "status": "Aberto",
                "severity": "Média",
                "description": "Wifi caindo no deposito.",
                "category_name": "Ubiquiti / Wi-Fi",
                "requester_login": "pedro.torres",
                "glpi_user_id": 1001,
                "channel": "web_simulator",
                "location": "TI - Matriz",
                "impact_label": "Afeta somente a mim",
                "evidence": "Não informado",
                "opening_mode": "Abertura assistida",
                "created_at": "2026-05-05T00:00:00Z",
                "followups": [],
            }

    def fake_description_apply_async(args, queue):
        return FakeDescriptionAsyncResult()

    def fake_ticket_apply_async(args, queue):
        return FakeTicketAsyncResult()

    monkeypatch.setattr(
        organize_description_task, "apply_async", fake_description_apply_async
    )
    monkeypatch.setattr(create_glpi_ticket_task, "apply_async", fake_ticket_apply_async)
    worker_ticket_store.clear()
    session_id = str(uuid4())
    controller = ConversationFlowController(
        settings=AppSettings(
            use_celery_workers=True,
            state_backend="memory",
            glpi_integration_mode="mock",
            local_light_ai_mode="mock",
            ai_guided_detailing_enabled=False,
        )
    )

    send(controller, session_id, "__start__")
    send(controller, session_id, "1")
    send(controller, session_id, "wifi caindo no deposito")
    send(controller, session_id, "1")
    send(controller, session_id, "1")
    send(controller, session_id, "2")
    send(controller, session_id, "TI - Matriz")
    send(controller, session_id, "2")
    created_response = send(controller, session_id, "1")

    assert created_response["created_ticket"]["ticket_number"] == 10001
    assert "Chamado simulado criado com sucesso" in created_response["bot_message"]
