from uuid import uuid4

from app.application_config.settings import AppSettings
from app.conversation_engine.conversation_flow_controller import ConversationFlowController
from app.local_light_ai.description_organization_models import (
    DescriptionOrganizationResult,
    GuidedDetailingResult,
    LocalGenerativeAIUnavailableError,
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


class UnavailableDetailer:
    def detail_ticket_description(
        self,
        original_description: str,
        clarification_turns: list[dict[str, str]],
        category_name: str | None,
        max_questions: int,
    ) -> GuidedDetailingResult:
        raise LocalGenerativeAIUnavailableError("offline")


class UnavailableOrganizer:
    def organize_ticket_description(
        self,
        user_text: str,
        category_name: str | None = None,
        purpose: str = "descricao_chamado",
    ) -> DescriptionOrganizationResult:
        raise LocalGenerativeAIUnavailableError("offline")


def send(controller: ConversationFlowController, session_id: str, message: str):
    return controller.process_message(session_id=session_id, message=message)


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


def test_guided_flow_asks_one_question_and_then_suggests_category() -> None:
    detailer = SequencedDetailer(
        [
            ask("Qual equipamento está afetado e o que acontece exatamente?"),
            ready("Estou com tela azul no notebook do financeiro."),
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
    clarification = send(
        controller,
        session_id,
        "Estou com problema no meu computador",
    )
    category = send(
        controller,
        session_id,
        "É o notebook do financeiro e aparece tela azul.",
    )

    assert clarification.state == "description_clarification"
    assert "Pergunta 1 de até 1" in clarification.bot_message
    assert category.state == "category_assignment_confirmation"
    assert "Computador / Notebook" in category.bot_message
    assert len(detailer.calls) == 1
    assert "É o notebook do financeiro" in category.bot_message


def test_guided_flow_proceeds_with_summary_when_user_skips_answer() -> None:
    detailer = SequencedDetailer(
        [ask("Qual erro aparece ou qual comportamento você percebe exatamente?")]
    )
    controller = ConversationFlowController(
        settings=AppSettings(ai_guided_detailing_enabled=True),
        description_organizer=EchoDescriptionOrganizer(),
        description_detailer=detailer,
    )
    session_id = str(uuid4())

    send(controller, session_id, "__start__")
    send(controller, session_id, "1")
    send(controller, session_id, "Estou com problema no meu computador")
    result = send(controller, session_id, "não sei")

    assert result.state == "category_assignment_confirmation"
    assert "Computador / Notebook" in result.bot_message
    assert len(detailer.calls) == 1


def test_guided_flow_stops_at_configured_question_limit() -> None:
    detailer = SequencedDetailer(
        [
            ask("Qual equipamento está afetado?"),
            ask("Qual erro aparece?"),
        ]
    )
    controller = ConversationFlowController(
        settings=AppSettings(
            ai_guided_detailing_enabled=True,
            ai_max_clarification_questions=2,
        ),
        description_organizer=EchoDescriptionOrganizer(),
        description_detailer=detailer,
    )
    session_id = str(uuid4())

    send(controller, session_id, "__start__")
    send(controller, session_id, "1")
    send(controller, session_id, "Estou com problema no meu computador")
    send(controller, session_id, "Notebook")
    result = send(controller, session_id, "Aparece tela azul")

    assert result.state == "category_assignment_confirmation"
    assert len(detailer.calls) == 2
    assert "Aparece tela azul" in result.bot_message
    assert "Qual equipamento" not in result.bot_message
    assert "Detalhe coletado" not in result.bot_message


def test_guided_flow_reset_clears_clarification_memory() -> None:
    detailer = SequencedDetailer([ask("Qual equipamento está afetado?")])
    controller = ConversationFlowController(
        settings=AppSettings(ai_guided_detailing_enabled=True),
        description_organizer=EchoDescriptionOrganizer(),
        description_detailer=detailer,
    )
    session_id = str(uuid4())

    send(controller, session_id, "__start__")
    send(controller, session_id, "1")
    send(controller, session_id, "Estou com problema no meu computador")
    send(controller, session_id, "reset")

    debug_context = controller.debug_session(session_id)

    assert debug_context is not None
    assert debug_context["state"] == "main_menu"
    assert debug_context["description_clarification_count"] == 0


def test_guided_flow_keeps_clarification_memory_isolated_between_sessions() -> None:
    detailer = SequencedDetailer(
        [
            ask("Qual item está afetado?"),
            ask("Qual item está afetado?"),
            ready("Estou com problema de nota. A nota não aparece para lançamento."),
        ]
    )
    controller = ConversationFlowController(
        settings=AppSettings(ai_guided_detailing_enabled=True),
        description_organizer=EchoDescriptionOrganizer(),
        description_detailer=detailer,
    )
    session_a = str(uuid4())
    session_b = str(uuid4())

    send(controller, session_a, "__start__")
    send(controller, session_a, "1")
    send(controller, session_a, "estou com um problema de nota")

    send(controller, session_b, "__start__")
    send(controller, session_b, "1")
    send(controller, session_b, "estou com um problema de impressora")

    result_a = send(controller, session_a, "A nota não aparece para lançamento.")
    debug_b = controller.debug_session(session_b)

    assert result_a.state == "category_assignment_confirmation"
    assert debug_b is not None
    assert debug_b["state"] == "description_clarification"
    assert debug_b["description_clarification_count"] == 0


def test_guided_flow_uses_collected_answer_instead_of_generic_original_summary() -> None:
    detailer = SequencedDetailer(
        [
            ask("O que acontece exatamente?"),
            ready("A nota fiscal não aparece para lançamento."),
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
    send(controller, session_id, "estou com um problema grave de nota")
    result = send(
        controller,
        session_id,
        "A nota fiscal não aparece para lançamento.",
    )

    assert result.state == "category_assignment_confirmation"
    assert "A nota fiscal não aparece para lançamento" in result.bot_message
    assert "problema grave de nota. A nota" not in result.bot_message
    assert "relatou que o problema é grave" not in result.bot_message
    assert "Considero o problema grave" in result.bot_message


def test_guided_flow_builds_first_person_summary_without_internal_text() -> None:
    detailer = SequencedDetailer(
        [ask("Poderia especificar qual erro aparece na nota?")]
    )
    controller = ConversationFlowController(
        settings=AppSettings(ai_guided_detailing_enabled=True),
        description_organizer=EchoDescriptionOrganizer(),
        description_detailer=detailer,
    )
    session_id = str(uuid4())

    send(controller, session_id, "__start__")
    send(controller, session_id, "1")
    send(controller, session_id, "Estou com um problema de nota")
    result = send(
        controller,
        session_id,
        "Estou com um problema que durante a visualizacao na tela 1234, a nota exibe o erro 123.456.789.",
    )

    assert result.state == "category_assignment_confirmation"
    assert "O usuario informou inicialmente" not in result.bot_message
    assert "Depois, acrescentou" not in result.bot_message
    assert "O usuario" not in result.bot_message
    assert "Estou com um problema de nota. Durante a visualizacao na tela 1234" in result.bot_message


def test_guided_flow_falls_back_when_local_ai_is_unavailable() -> None:
    controller = ConversationFlowController(
        settings=AppSettings(ai_guided_detailing_enabled=True),
        description_organizer=UnavailableOrganizer(),
        description_detailer=UnavailableDetailer(),
    )
    session_id = str(uuid4())

    send(controller, session_id, "__start__")
    send(controller, session_id, "1")
    result = send(controller, session_id, "Preciso de acesso ao sistema financeiro")

    assert result.state == "category_assignment_confirmation"
    assert "Preciso de acesso ao sistema financeiro." in result.bot_message
