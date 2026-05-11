from uuid import uuid4

from app.application_config.settings import AppSettings
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
        settings=AppSettings(ai_guided_detailing_enabled=False),
        description_organizer=FakeDescriptionOrganizer()
    )
    session_id = str(uuid4())

    controller.process_message(session_id, "__start__")
    result = controller.process_message(session_id, "abrir chamado")

    assert result.state == "main_menu"
    assert "número" in result.bot_message


def test_category_assignment_rejects_unavailable_choice() -> None:
    controller = ConversationFlowController(
        settings=AppSettings(ai_guided_detailing_enabled=False),
        description_organizer=FakeDescriptionOrganizer()
    )
    session_id = str(uuid4())

    controller.process_message(session_id, "__start__")
    controller.process_message(session_id, "1")
    controller.process_message(session_id, "wifi caindo no deposito")
    result = controller.process_message(session_id, "9")

    assert result.state == "description_review"
    assert "não está disponível" in result.bot_message


def test_location_requires_text_not_menu_number() -> None:
    controller = ConversationFlowController(
        settings=AppSettings(ai_guided_detailing_enabled=False),
        description_organizer=FakeDescriptionOrganizer()
    )
    session_id = str(uuid4())

    controller.process_message(session_id, "__start__")
    controller.process_message(session_id, "1")
    controller.process_message(session_id, "wifi caindo no deposito")
    controller.process_message(session_id, "1")
    result = controller.process_message(session_id, "1")

    assert result.state == "location_collection"
    assert "localidade que deve constar no chamado" in result.bot_message


def test_greeting_returns_main_menu_instead_of_invalid_choice() -> None:
    controller = ConversationFlowController(
        settings=AppSettings(ai_guided_detailing_enabled=False),
        description_organizer=FakeDescriptionOrganizer()
    )
    session_id = str(uuid4())

    result = controller.process_message(session_id, "Olá")

    assert result.state == "main_menu"
    assert "Abrir um novo chamado" in result.bot_message
    assert "nÃºmero" not in result.bot_message
