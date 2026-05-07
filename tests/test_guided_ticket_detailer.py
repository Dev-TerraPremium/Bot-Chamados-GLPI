from app.local_light_ai.guided_ticket_detailer import GuidedTicketDetailer


class FakeGenerativeClient:
    def __init__(self, payload: dict) -> None:
        self.payload = payload
        self.called = False
        self.user_prompt = ""

    def generate_json(self, system_prompt: str, user_prompt: str, options: dict) -> dict:
        self.called = True
        self.user_prompt = user_prompt
        return self.payload


def test_guided_detailer_returns_safe_next_question() -> None:
    detailer = GuidedTicketDetailer(
        client=FakeGenerativeClient(
            {
                "status": "ask_next",
                "next_question": "Qual equipamento está afetado e qual erro aparece?",
                "organized_text": "",
                "confidence": 0.81,
            }
        ),
        backend_name="fake-generative",
    )

    result = detailer.detail_ticket_description(
        original_description="Estou com problema no meu computador",
        clarification_turns=[],
        category_name=None,
        max_questions=5,
    )

    assert result.asks_next
    assert result.next_question.endswith("?")
    assert "senha" not in result.next_question.casefold()


def test_guided_detailer_replaces_unsafe_question_with_fallback() -> None:
    detailer = GuidedTicketDetailer(
        client=FakeGenerativeClient(
            {
                "status": "ask_next",
                "next_question": "Qual sua senha atual para eu testar?",
                "organized_text": "",
                "confidence": 0.9,
            }
        ),
        backend_name="fake-generative",
    )

    result = detailer.detail_ticket_description(
        original_description="Não consigo acessar o sistema",
        clarification_turns=[],
        category_name=None,
        max_questions=5,
    )

    assert result.asks_next
    assert "senha" not in result.next_question.casefold()
    assert "o que acontece" in result.next_question.casefold()


def test_guided_detailer_finalizes_when_question_limit_is_reached() -> None:
    client = FakeGenerativeClient(
        {
            "status": "ask_next",
            "next_question": "Qual erro aparece?",
            "organized_text": "",
            "confidence": 0.9,
        }
    )
    detailer = GuidedTicketDetailer(client=client, backend_name="fake-generative")

    result = detailer.detail_ticket_description(
        original_description="Estou com problema no computador",
        clarification_turns=[
            {"question": "Qual equipamento?", "answer": "Notebook"},
            {"question": "Qual erro?", "answer": "Tela azul"},
        ],
        category_name=None,
        max_questions=2,
    )

    assert result.is_ready
    assert not client.called
    assert "Notebook" in result.organized_text


def test_guided_detailer_uses_compact_summary_when_ready_payload_is_empty() -> None:
    detailer = GuidedTicketDetailer(
        client=FakeGenerativeClient(
            {
                "status": "ready",
                "next_question": "",
                "organized_text": "",
                "confidence": 0.7,
            }
        ),
        backend_name="fake-generative",
    )

    result = detailer.detail_ticket_description(
        original_description="Estou com problema no computador",
        clarification_turns=[
            {
                "question": "Qual equipamento está afetado?",
                "answer": "Notebook do financeiro",
            }
        ],
        category_name=None,
        max_questions=5,
    )

    assert result.is_ready
    assert "Notebook do financeiro" in result.organized_text


def test_guided_detailer_does_not_accept_ready_for_vague_initial_text() -> None:
    detailer = GuidedTicketDetailer(
        client=FakeGenerativeClient(
            {
                "status": "ready",
                "next_question": "",
                "organized_text": "O problema no computador foi resolvido.",
                "confidence": 0.9,
            }
        ),
        backend_name="fake-generative",
    )

    result = detailer.detail_ticket_description(
        original_description="Estou com problema no meu computador",
        clarification_turns=[],
        category_name=None,
        max_questions=5,
    )

    assert result.asks_next
    assert "o que acontece" in result.next_question.casefold()


def test_guided_detailer_asks_question_for_generic_problem_of_something() -> None:
    detailer = GuidedTicketDetailer(
        client=FakeGenerativeClient(
            {
                "status": "ready",
                "next_question": "",
                "organized_text": "O usuário está com um problema de nota.",
                "confidence": 0.9,
            }
        ),
        backend_name="fake-generative",
    )

    result = detailer.detail_ticket_description(
        original_description="estou com um problema de nota",
        clarification_turns=[],
        category_name=None,
        max_questions=5,
    )

    assert result.asks_next
    assert "o que acontece" in result.next_question.casefold()


def test_guided_detailer_asks_question_for_generic_problem_with_qualifier() -> None:
    detailer = GuidedTicketDetailer(
        client=FakeGenerativeClient(
            {
                "status": "ready",
                "next_question": "",
                "organized_text": "Estou com um problema grave de nota.",
                "confidence": 0.9,
            }
        ),
        backend_name="fake-generative",
    )

    result = detailer.detail_ticket_description(
        original_description="estou com um problema grave de nota",
        clarification_turns=[],
        category_name=None,
        max_questions=5,
    )

    assert result.asks_next
    assert "o que acontece" in result.next_question.casefold()


def test_guided_detailer_replaces_diagnostic_ready_text_with_compact_summary() -> None:
    detailer = GuidedTicketDetailer(
        client=FakeGenerativeClient(
            {
                "status": "ready",
                "next_question": "",
                "organized_text": "O problema é causado pelo notebook do financeiro.",
                "confidence": 0.9,
            }
        ),
        backend_name="fake-generative",
    )

    result = detailer.detail_ticket_description(
        original_description="Estou com problema no computador",
        clarification_turns=[
            {
                "question": "Qual equipamento está afetado?",
                "answer": "Notebook do financeiro com tela azul",
            }
        ],
        category_name=None,
        max_questions=5,
    )

    assert result.is_ready
    assert "causado" not in result.organized_text.casefold()
    assert "Notebook do financeiro" in result.organized_text


def test_guided_detailer_replaces_speculative_ready_text_with_compact_summary() -> None:
    detailer = GuidedTicketDetailer(
        client=FakeGenerativeClient(
            {
                "status": "ready",
                "next_question": "",
                "organized_text": "A tela azul pode indicar problema no sistema.",
                "confidence": 0.9,
            }
        ),
        backend_name="fake-generative",
    )

    result = detailer.detail_ticket_description(
        original_description="Estou com problema no computador",
        clarification_turns=[
            {
                "question": "Qual equipamento está afetado?",
                "answer": "Notebook do financeiro com tela azul ao iniciar",
            }
        ],
        category_name=None,
        max_questions=5,
    )

    assert result.is_ready
    assert "pode indicar" not in result.organized_text.casefold()
    assert "Notebook do financeiro" in result.organized_text


def test_guided_detailer_rejects_unsupported_terms_from_ready_text() -> None:
    detailer = GuidedTicketDetailer(
        client=FakeGenerativeClient(
            {
                "status": "ready",
                "next_question": "",
                "organized_text": "O sistema está configurado para gerenciar a rede Wi-Fi.",
                "confidence": 0.9,
            }
        ),
        backend_name="fake-generative",
    )

    result = detailer.detail_ticket_description(
        original_description="Wi-Fi caindo no depósito",
        clarification_turns=[],
        category_name=None,
        max_questions=5,
    )

    assert result.is_ready
    assert "sistema" not in result.organized_text.casefold()
    assert "Wi-Fi caindo" in result.organized_text


def test_guided_detailer_does_not_send_category_context_to_model() -> None:
    client = FakeGenerativeClient(
        {
            "status": "ready",
            "next_question": "",
            "organized_text": "Categoria não informada.",
            "confidence": 0.9,
        }
    )
    detailer = GuidedTicketDetailer(client=client, backend_name="fake-generative")

    detailer.detail_ticket_description(
        original_description="estou com um problema grave de nota",
        clarification_turns=[
            {
                "question": "O que acontece exatamente?",
                "answer": "A nota não aparece para lançamento.",
            }
        ],
        category_name="Outro",
        max_questions=5,
    )

    assert "categoria" not in client.user_prompt.casefold()


def test_guided_detailer_accepts_model_contextual_question_without_domain_rules() -> None:
    detailer = GuidedTicketDetailer(
        client=FakeGenerativeClient(
            {
                "status": "ask_next",
                "next_question": (
                    "Esse pedido e para corrigir algo que falhou, substituir algo "
                    "existente ou atender uma nova necessidade?"
                ),
                "organized_text": "",
                "confidence": 0.9,
            }
        ),
        backend_name="fake-generative",
    )

    result = detailer.detail_ticket_description(
        original_description="Solicito a compra de um kit mouse e teclado.",
        clarification_turns=[],
        category_name=None,
        max_questions=5,
    )

    assert result.asks_next
    assert "substituir" in result.next_question.casefold() or "nova necessidade" in result.next_question.casefold()


def test_guided_detailer_prompt_uses_generic_triage_dimensions() -> None:
    client = FakeGenerativeClient(
        {
            "status": "ready",
            "next_question": "",
            "organized_text": "",
            "confidence": 0.9,
        }
    )
    detailer = GuidedTicketDetailer(client=client, backend_name="fake-generative")

    detailer.detail_ticket_description(
        original_description="Solicito a compra de um kit.",
        clarification_turns=[],
        category_name=None,
        max_questions=5,
    )

    prompt = client.user_prompt.casefold()
    assert "qualidade do chamado final" in prompt
    assert "proximo passo" in prompt
