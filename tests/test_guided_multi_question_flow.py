from uuid import uuid4

from app.application_config.settings import AppSettings
from app.conversation_engine.conversation_flow_controller import ConversationFlowController
from app.local_light_ai.description_organization_models import (
    DescriptionOrganizationResult,
    GuidedDetailingResult,
)


class EchoDescriptionOrganizer:
    def organize_ticket_description(
        self,
        user_text: str,
        category_name: str | None = None,
        purpose: str = "descricao_chamado",
    ) -> DescriptionOrganizationResult:
        return DescriptionOrganizationResult(
            status="organized",
            organized_text=user_text,
            clarification_question="",
            confidence=0.9,
            backend="fake-generative",
        )


class SequencedDetailer:
    def __init__(self, results: list[GuidedDetailingResult]) -> None:
        self.results = results
        self.calls: list[dict] = []

    def detail_ticket_description(
        self,
        original_description: str,
        clarification_turns: list[dict[str, str]],
        category_name: str | None,
        max_questions: int,
    ) -> GuidedDetailingResult:
        self.calls.append(
            {
                "original_description": original_description,
                "clarification_turns": list(clarification_turns),
                "max_questions": max_questions,
            }
        )
        return self.results.pop(0)


def ask(question: str) -> GuidedDetailingResult:
    return GuidedDetailingResult(
        status="ask_next",
        next_question=question,
        organized_text="",
        confidence=0.8,
        backend="fake-generative",
    )


def ready(text: str) -> GuidedDetailingResult:
    return GuidedDetailingResult(
        status="ready",
        next_question="",
        organized_text=text,
        confidence=0.9,
        backend="fake-generative",
    )


def send(controller: ConversationFlowController, session_id: str, message: str):
    return controller.process_message(session_id=session_id, message=message)


def test_guided_flow_can_ask_two_contextual_questions_before_finalizing() -> None:
    detailer = SequencedDetailer(
        [
            ask("Poderia me detalhar o que está acontecendo exatamente?"),
            ask("Qual sistema ou funcionalidade exatamente apresenta esse comportamento?"),
            ready(
                "Estou com um problema. "
                "Ele fecha toda hora quando tento usar. "
                "Isso acontece no Outlook."
            ),
        ]
    )
    controller = ConversationFlowController(
        settings=AppSettings(ai_guided_detailing_enabled=True),
        description_organizer=EchoDescriptionOrganizer(),
        description_detailer=detailer,
    )
    session_id = str(uuid4())

    send(controller, session_id, "__start__")
    send(controller, session_id, "1")
    first_question = send(controller, session_id, "Estou com um problema")
    second_question = send(controller, session_id, "Ele fecha toda hora quando tento usar")
    result = send(controller, session_id, "Isso acontece no Outlook")

    assert first_question.state == "description_clarification"
    assert first_question.bot_message == "Poderia me detalhar o que está acontecendo exatamente?"
    assert second_question.state == "description_clarification"
    assert second_question.bot_message == "Qual sistema ou funcionalidade exatamente apresenta esse comportamento?"
    assert result.state == "description_review"
    assert "Outlook" in result.bot_message
    assert len(detailer.calls) == 3
