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
        category_name="Solicitacao de equipamento",
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
                "clarification_question": "Pode explicar qual equipamento ou acesso voce precisa?",
                "confidence": 0.31,
            }
        ),
        backend_name="fake-generative",
    )

    result = organizer.organize_ticket_description("frase que nao tem sentido")

    assert result.needs_clarification
    assert "explicar" in result.clarification_question
