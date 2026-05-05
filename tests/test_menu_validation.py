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
            organized_text="Wi-Fi caindo no depósito.",
            clarification_question="",
            confidence=0.9,
            backend="fake-generative",
        )


def test_main_menu_rejects_text_when_choice_is_required() -> None:
    controller = ConversationFlowController(
        description_organizer=FakeDescriptionOrganizer()
    )
    session_id = str(uuid4())

    controller.process_message(session_id, "__start__")
    result = controller.process_message(session_id, "abrir chamado")

    assert result.state == "main_menu"
    assert "número" in result.bot_message


def test_category_assignment_rejects_unavailable_choice() -> None:
    controller = ConversationFlowController(
        description_organizer=FakeDescriptionOrganizer()
    )
    session_id = str(uuid4())

    controller.process_message(session_id, "__start__")
    controller.process_message(session_id, "1")
    controller.process_message(session_id, "wifi caindo no deposito")
    result = controller.process_message(session_id, "9")

    assert result.state == "category_assignment_confirmation"
    assert "não está disponível" in result.bot_message


def test_location_requires_text_not_menu_number() -> None:
    controller = ConversationFlowController(
        description_organizer=FakeDescriptionOrganizer()
    )
    session_id = str(uuid4())

    controller.process_message(session_id, "__start__")
    controller.process_message(session_id, "1")
    controller.process_message(session_id, "wifi caindo no deposito")
    controller.process_message(session_id, "1")
    controller.process_message(session_id, "1")
    controller.process_message(session_id, "2")
    result = controller.process_message(session_id, "1")

    assert result.state == "location_collection"
    assert "setor ou localidade" in result.bot_message
