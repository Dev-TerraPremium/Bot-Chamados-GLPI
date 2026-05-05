from app.local_light_ai.generative_description_organizer import (
    GenerativeDescriptionOrganizer,
)


class FakeGenerativeClient:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def generate_json(self, system_prompt: str, user_prompt: str, options: dict) -> dict:
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
