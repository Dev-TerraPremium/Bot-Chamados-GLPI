from app.local_light_ai.generative_description_organizer import (
    GenerativeDescriptionOrganizer,
)


class FakeGenerativeClient:
    def __init__(self, payload: dict) -> None:
        self.payload = payload
        self.user_prompt = ""

    def generate_json(self, system_prompt: str, user_prompt: str, options: dict) -> dict:
        self.user_prompt = user_prompt
        return self.payload


def test_generative_organizer_returns_organized_description() -> None:
    organizer = GenerativeDescriptionOrganizer(
        client=FakeGenerativeClient(
            {
                "status": "organized",
                "organized_text": "Preciso solicitar um desktop novo para mim.",
                "clarification_question": "",
                "confidence": 0.82,
            }
        ),
        backend_name="fake-generative",
    )

    result = organizer.organize_ticket_description(
        "Preciso realizar um desktopi nov para mim",
        category_name="Solicitação de equipamento",
    )

    assert result.is_organized
    assert result.organized_text == "Preciso solicitar um desktop novo para mim."
    assert result.backend == "fake-generative"


def test_generative_organizer_can_request_clarification() -> None:
    organizer = GenerativeDescriptionOrganizer(
        client=FakeGenerativeClient(
            {
                "status": "needs_clarification",
                "organized_text": "",
                "clarification_question": "Pode explicar qual equipamento ou acesso você precisa?",
                "confidence": 0.31,
            }
        ),
        backend_name="fake-generative",
    )

    result = organizer.organize_ticket_description("frase que não tem sentido")

    assert result.needs_clarification
    assert "explicar" in result.clarification_question


def test_generative_organizer_rejects_invented_negative_diagnosis() -> None:
    organizer = GenerativeDescriptionOrganizer(
        client=FakeGenerativeClient(
            {
                "status": "organized",
                "organized_text": "Seu problema grave no desktop não foi identificado.",
                "clarification_question": "",
                "confidence": 0.9,
            }
        ),
        backend_name="fake-generative",
    )

    result = organizer.organize_ticket_description(
        "Estou com problema grave no meu desktop"
    )

    assert result.needs_clarification
    assert "segurança" in result.clarification_question


def test_generative_organizer_rejects_invented_resolution() -> None:
    organizer = GenerativeDescriptionOrganizer(
        client=FakeGenerativeClient(
            {
                "status": "organized",
                "organized_text": "O problema no computador foi identificado e resolvido.",
                "clarification_question": "",
                "confidence": 0.9,
            }
        ),
        backend_name="fake-generative",
    )

    result = organizer.organize_ticket_description(
        "Estou com problema no meu computador"
    )

    assert result.needs_clarification
    assert "segurança" in result.clarification_question


def test_generative_organizer_rejects_invented_cause() -> None:
    organizer = GenerativeDescriptionOrganizer(
        client=FakeGenerativeClient(
            {
                "status": "organized",
                "organized_text": "O problema no computador é causado pelo notebook.",
                "clarification_question": "",
                "confidence": 0.9,
            }
        ),
        backend_name="fake-generative",
    )

    result = organizer.organize_ticket_description(
        "Estou com problema no meu computador"
    )

    assert result.needs_clarification
    assert "segurança" in result.clarification_question


def test_generative_organizer_rejects_speculative_diagnosis() -> None:
    organizer = GenerativeDescriptionOrganizer(
        client=FakeGenerativeClient(
            {
                "status": "organized",
                "organized_text": "A tela azul pode indicar problema no sistema.",
                "clarification_question": "",
                "confidence": 0.9,
            }
        ),
        backend_name="fake-generative",
    )

    result = organizer.organize_ticket_description(
        "Notebook do financeiro com tela azul ao iniciar"
    )

    assert result.needs_clarification
    assert "segurança" in result.clarification_question


def test_generative_organizer_rejects_unsupported_terms() -> None:
    organizer = GenerativeDescriptionOrganizer(
        client=FakeGenerativeClient(
            {
                "status": "organized",
                "organized_text": "O sistema está configurado para gerenciar a rede Wi-Fi.",
                "clarification_question": "",
                "confidence": 0.9,
            }
        ),
        backend_name="fake-generative",
    )

    result = organizer.organize_ticket_description("Wi-Fi caindo no depósito")

    assert result.needs_clarification
    assert "segurança" in result.clarification_question


def test_generative_organizer_does_not_send_category_context_to_model() -> None:
    client = FakeGenerativeClient(
        {
            "status": "organized",
            "organized_text": "Estou com um problema grave de nota.",
            "clarification_question": "",
            "confidence": 0.9,
        }
    )
    organizer = GenerativeDescriptionOrganizer(
        client=client,
        backend_name="fake-generative",
    )

    result = organizer.organize_ticket_description(
        "estou com um problema grave de nota",
        category_name="Outro",
    )

    assert result.is_organized
    assert "categoria" not in client.user_prompt.casefold()


def test_generative_organizer_rejects_category_leak() -> None:
    organizer = GenerativeDescriptionOrganizer(
        client=FakeGenerativeClient(
            {
                "status": "organized",
                "organized_text": (
                    "O usuário está com um problema grave de nota, "
                    "mas não foi informado na categoria."
                ),
                "clarification_question": "",
                "confidence": 0.9,
            }
        ),
        backend_name="fake-generative",
    )

    result = organizer.organize_ticket_description(
        "estou com um problema grave de nota"
    )

    assert result.needs_clarification
    assert "segurança" in result.clarification_question


def test_generative_organizer_limits_input_and_output() -> None:
    organizer = GenerativeDescriptionOrganizer(
        client=FakeGenerativeClient(
            {
                "status": "organized",
                "organized_text": "x" * 50,
                "clarification_question": "",
                "confidence": 0.9,
            }
        ),
        backend_name="fake-generative",
        max_input_chars=10,
        max_output_chars=20,
    )

    input_result = organizer.organize_ticket_description("x" * 11)
    assert input_result.needs_clarification

    organizer.max_input_chars = 100
    output_result = organizer.organize_ticket_description("texto curto")
    assert output_result.needs_clarification


def test_system_prompt_guides_broken_desktop_text() -> None:
    prompt = GenerativeDescriptionOrganizer._build_system_prompt()

    assert "Estou com um problema grave no meu desktop." in prompt
    assert "Preciso solicitar um desktop novo para mim." in prompt
    assert "Seu problema não foi identificado" in prompt
    assert "Nunca comece com 'Realize'" in prompt
