from uuid import uuid4

from app.application_config.settings import AppSettings
from app.conversation_engine.conversation_flow_controller import (
    ConversationFlowController,
)
from app.local_light_ai.description_organization_models import (
    DescriptionOrganizationResult,
)


class ClarificationDescriptionOrganizer:
    def organize_ticket_description(
        self,
        user_text: str,
        category_name: str | None = None,
        purpose: str = "descricao_chamado",
    ) -> DescriptionOrganizationResult:
        return DescriptionOrganizationResult(
            status="needs_clarification",
            organized_text="",
            clarification_question="Pode explicar melhor o que precisa registrar?",
            confidence=0.2,
            backend="fake-generative",
        )


def test_description_collection_asks_for_clarification_when_text_is_broken() -> None:
    controller = ConversationFlowController(
        settings=AppSettings(ai_guided_detailing_enabled=False),
        description_organizer=ClarificationDescriptionOrganizer()
    )
    session_id = str(uuid4())

    controller.process_message(session_id, "__start__")
    controller.process_message(session_id, "1")
    result = controller.process_message(
        session_id,
        "Preciso realizar um desktopi nov para mim",
    )

    assert result.state == "description_collection"
    assert "explicar melhor" in result.bot_message
