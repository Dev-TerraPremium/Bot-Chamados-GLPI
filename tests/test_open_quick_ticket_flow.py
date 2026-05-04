from uuid import uuid4

from app.conversation_engine.conversation_flow_controller import (
    ConversationFlowController,
)
from app.local_light_ai.description_organization_models import (
    DescriptionOrganizationResult,
)


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


def send(controller: ConversationFlowController, session_id: str, message: str) -> dict:
    result = controller.process_message(session_id=session_id, message=message)
    return {
        "session_id": result.session_id,
        "bot_message": result.bot_message,
        "state": result.state,
        "ticket_preview": result.ticket_preview,
        "created_ticket": result.created_ticket,
    }


def test_open_quick_ticket_flow_creates_simulated_ticket() -> None:
    session_id = str(uuid4())
    controller = ConversationFlowController(
        description_organizer=FakeDescriptionOrganizer()
    )

    send(controller, session_id, "__start__")
    send(controller, session_id, "1")
    send(controller, session_id, "1")
    category_response = send(controller, session_id, "wifi caindo no deposito")
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
