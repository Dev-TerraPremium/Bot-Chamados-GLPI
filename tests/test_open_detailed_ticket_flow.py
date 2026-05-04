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
            organized_text="Estou com meu acesso a pasta RH bloqueado.",
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


def test_open_detailed_ticket_flow_creates_simulated_ticket() -> None:
    session_id = str(uuid4())
    controller = ConversationFlowController(
        description_organizer=FakeDescriptionOrganizer()
    )

    start_response = send(controller, session_id, "__start__")
    assert "pedro.torres" in start_response["bot_message"]

    send(controller, session_id, "1")
    send(controller, session_id, "2")
    send(controller, session_id, "6")
    review_response = send(
        controller,
        session_id,
        "Estou com meu acesso a pasta RH bloqueado",
    )
    assert "acesso a pasta RH bloqueado." in review_response["bot_message"]

    send(controller, session_id, "1")
    send(controller, session_id, "3")
    send(controller, session_id, "RH - Rondonopolis")
    summary_response = send(controller, session_id, "2")

    assert summary_response["state"] == "final_confirmation"
    assert summary_response["ticket_preview"]["severity"] == "Alta"
    assert summary_response["ticket_preview"]["category"] == "Acesso / Senha"

    created_response = send(controller, session_id, "1")
    assert created_response["created_ticket"]["severity"] == "Alta"
    assert created_response["created_ticket"]["glpi_user_id"] == 1001
