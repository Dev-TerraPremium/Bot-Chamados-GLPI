import httpx

from app.local_light_ai.generative_description_organizer import (
    GenerativeDescriptionOrganizer,
    GoogleAILocalGenerativeClient,
)
from app.local_light_ai.description_organization_models import (
    LocalGenerativeAIUnavailableError,
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


def test_generative_organizer_rejects_invented_negative_diagnosis() -> None:
    organizer = GenerativeDescriptionOrganizer(
        client=FakeGenerativeClient(
            {
                "status": "organized",
                "organized_text": "Seu problema grave no desktop nao foi identificado.",
                "clarification_question": "",
                "confidence": 0.9,
            }
        ),
        backend_name="fake-generative",
    )

    result = organizer.organize_ticket_description(
        "Estou com problema grave no meu desktop"
    )

    assert result.is_organized
    assert result.organized_text == "Estou com problema grave no meu desktop."


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

    assert result.is_organized
    assert result.organized_text == "Estou com problema no meu computador."


def test_generative_organizer_rejects_invented_cause() -> None:
    organizer = GenerativeDescriptionOrganizer(
        client=FakeGenerativeClient(
            {
                "status": "organized",
                "organized_text": "O problema no computador e causado pelo notebook.",
                "clarification_question": "",
                "confidence": 0.9,
            }
        ),
        backend_name="fake-generative",
    )

    result = organizer.organize_ticket_description(
        "Estou com problema no meu computador"
    )

    assert result.is_organized
    assert result.organized_text == "Estou com problema no meu computador."


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

    assert result.is_organized
    assert result.organized_text == "Notebook do financeiro com tela azul ao iniciar."


def test_generative_organizer_rejects_unsupported_terms() -> None:
    organizer = GenerativeDescriptionOrganizer(
        client=FakeGenerativeClient(
            {
                "status": "organized",
                "organized_text": "O sistema esta configurado para gerenciar a rede Wi-Fi.",
                "clarification_question": "",
                "confidence": 0.9,
            }
        ),
        backend_name="fake-generative",
    )

    result = organizer.organize_ticket_description("Wi-Fi caindo no deposito")

    assert result.is_organized
    assert result.organized_text == "Wi-Fi caindo no deposito."


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
                    "O usuario esta com um problema grave de nota, "
                    "mas nao foi informado na categoria."
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

    assert result.is_organized
    assert result.organized_text == "estou com um problema grave de nota."


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

    assert "Responda somente JSON" in prompt
    assert "primeira pessoa" in prompt
    assert "Use organized" in prompt
    assert "Use needs_clarification" in prompt
    assert "o usuario" in prompt
    assert "provavelmente" in prompt


def test_user_prompt_requires_first_person_and_preserves_error_codes() -> None:
    prompt = GenerativeDescriptionOrganizer._build_user_prompt(
        "Estou com problema de nota na tela 1234 com erro 123.456.789",
        category_name=None,
        purpose="descricao_chamado",
    )

    assert "primeira pessoa" in prompt
    assert "123.456.789" in prompt
    assert "Exemplo proibido" in prompt


def test_generative_organizer_rewrites_internal_third_person_as_fallback() -> None:
    organizer = GenerativeDescriptionOrganizer(
        client=FakeGenerativeClient(
            {
                "status": "organized",
                "organized_text": "O usuario informou que esta com problema de nota.",
                "clarification_question": "",
                "confidence": 0.9,
            }
        ),
        backend_name="fake-generative",
    )

    result = organizer.organize_ticket_description(
        "Estou com problema de nota. Durante a visualizacao na tela 1234, a nota exibe o erro 123.456.789."
    )

    assert result.is_organized
    assert result.organized_text.startswith("Estou com problema de nota.")
    assert "O usuario" not in result.organized_text


def test_generative_organizer_accepts_portuguese_status_and_percentage_confidence() -> None:
    organizer = GenerativeDescriptionOrganizer(
        client=FakeGenerativeClient(
            {
                "status": "organizado",
                "organized_text": "Preciso de acesso ao sistema financeiro.",
                "clarification_question": "",
                "confidence": "95%",
            }
        ),
        backend_name="fake-generative",
    )

    result = organizer.organize_ticket_description(
        "Preciso de acesso ao sistema financeiro"
    )

    assert result.is_organized
    assert result.confidence == 0.95


def test_generative_organizer_prefers_organized_text_for_clear_longer_input() -> None:
    organizer = GenerativeDescriptionOrganizer(
        client=FakeGenerativeClient(
            {
                "status": "needs_clarification",
                "organized_text": "Preciso de acesso ao sistema financeiro para lancar notas fiscais.",
                "clarification_question": "O que voce esta procurando?",
                "confidence": 0.6,
            }
        ),
        backend_name="fake-generative",
    )

    result = organizer.organize_ticket_description(
        "Preciso de acesso ao sistema financeiro para lancar notas fiscais"
    )

    assert result.is_organized


def test_google_client_retries_transient_503(monkeypatch) -> None:
    calls = {"count": 0}

    class FakeResponse:
        def __init__(self, status_code: int, payload: dict) -> None:
            self.status_code = status_code
            self._payload = payload
            self.request = httpx.Request("POST", "https://example.test")

        def raise_for_status(self) -> None:
            if self.status_code >= 400:
                raise httpx.HTTPStatusError(
                    "boom",
                    request=self.request,
                    response=self,
                )

        def json(self) -> dict:
            return self._payload

    def fake_post(*args, **kwargs):
        calls["count"] += 1
        if calls["count"] == 1:
            return FakeResponse(503, {})
        return FakeResponse(
            200,
            {
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {
                                    "text": (
                                        '{"status":"organized","organized_text":"Wi-Fi caindo no deposito.",'
                                        '"clarification_question":"","confidence":0.9}'
                                    )
                                }
                            ]
                        }
                    }
                ]
            },
        )

    monkeypatch.setattr(httpx, "post", fake_post)
    monkeypatch.setattr("time.sleep", lambda *_args, **_kwargs: None)

    client = GoogleAILocalGenerativeClient(
        base_url="https://example.test",
        model="gemini-test",
        api_key="token",
        timeout_seconds=5,
        max_retries=1,
    )

    payload = client.generate_json(
        system_prompt="sys",
        user_prompt="user",
        options={"num_predict": 120},
    )

    assert calls["count"] == 2
    assert payload["status"] == "organized"


def test_google_client_does_not_retry_timeout(monkeypatch) -> None:
    calls = {"count": 0}

    def fake_post(*args, **kwargs):
        calls["count"] += 1
        raise httpx.TimeoutException("slow")

    monkeypatch.setattr(httpx, "post", fake_post)

    client = GoogleAILocalGenerativeClient(
        base_url="https://example.test",
        model="gemini-test",
        api_key="token",
        timeout_seconds=5,
        max_retries=1,
    )

    try:
        client.generate_json(
            system_prompt="sys",
            user_prompt="user",
            options={"num_predict": 120},
        )
    except LocalGenerativeAIUnavailableError:
        pass
    else:
        raise AssertionError("Expected Google timeout to fail fast")

    assert calls["count"] == 1
