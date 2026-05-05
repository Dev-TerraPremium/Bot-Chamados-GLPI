import json
import re
import unicodedata
from typing import Any, Protocol

import httpx

from app.application_config.settings import AppSettings
from app.local_light_ai.description_organization_models import (
    DescriptionOrganizationResult,
    LocalGenerativeAIUnavailableError,
)


class LocalGenerativeClient(Protocol):
    def generate_json(
        self,
        system_prompt: str,
        user_prompt: str,
        options: dict[str, Any],
    ) -> dict[str, Any]:
        pass


class MockLocalGenerativeClient:
    def generate_json(
        self,
        system_prompt: str,
        user_prompt: str,
        options: dict[str, Any],
    ) -> dict[str, Any]:
        user_text_prefix = "Texto original do usuário:"
        user_text = user_prompt.split(user_text_prefix, maxsplit=1)[-1]
        user_text = user_text.split("Organize somente o texto original.", maxsplit=1)[0]
        normalized_text = " ".join(user_text.strip().split())
        if not normalized_text:
            return {
                "status": "needs_clarification",
                "organized_text": "",
                "clarification_question": (
                    "Pode descrever o problema ou solicitação em uma frase curta?"
                ),
                "confidence": 0.0,
            }

        if not normalized_text.endswith((".", "!", "?")):
            normalized_text += "."

        return {
            "status": "organized",
            "organized_text": normalized_text[0].upper() + normalized_text[1:],
            "clarification_question": "",
            "confidence": 0.99,
        }


class OllamaLocalGenerativeClient:
    def __init__(
        self,
        base_url: str,
        model: str,
        timeout_seconds: float,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_seconds = timeout_seconds

    def generate_json(
        self,
        system_prompt: str,
        user_prompt: str,
        options: dict[str, Any],
    ) -> dict[str, Any]:
        payload = {
            "model": self.model,
            "system": system_prompt,
            "prompt": user_prompt,
            "stream": False,
            "format": "json",
            "options": options,
        }
        try:
            response = httpx.post(
                f"{self.base_url}/api/generate",
                json=payload,
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise LocalGenerativeAIUnavailableError(
                "Não foi possível acionar a IA generativa local via Ollama."
            ) from exc

        response_payload = response.json()
        raw_response = (
            response_payload.get("response")
            or response_payload.get("thinking")
            or ""
        )
        try:
            return json.loads(raw_response)
        except json.JSONDecodeError as exc:
            raise LocalGenerativeAIUnavailableError(
                "A IA generativa local retornou uma resposta fora do formato esperado."
            ) from exc


class GenerativeDescriptionOrganizer:
    """Local generative organizer for ticket descriptions."""

    def __init__(
        self,
        client: LocalGenerativeClient,
        backend_name: str,
        max_input_chars: int = 1000,
        max_output_chars: int = 800,
        num_predict: int = 180,
        temperature: float = 0.1,
    ) -> None:
        self.client = client
        self.backend_name = backend_name
        self.max_input_chars = max_input_chars
        self.max_output_chars = max_output_chars
        self.num_predict = num_predict
        self.temperature = temperature

    def organize_ticket_description(
        self,
        user_text: str,
        category_name: str | None = None,
        purpose: str = "descricao_chamado",
    ) -> DescriptionOrganizationResult:
        if len(user_text) > self.max_input_chars:
            return DescriptionOrganizationResult(
                status="needs_clarification",
                organized_text="",
                clarification_question=(
                    "Sua descrição está muito longa para a IA local. "
                    "Envie um resumo mais curto do problema."
                ),
                confidence=0.0,
                backend=self.backend_name,
            )
        model_payload = self.client.generate_json(
            system_prompt=self._build_system_prompt(),
            user_prompt=self._build_user_prompt(user_text, category_name, purpose),
            options={
                "temperature": self.temperature,
                "top_p": 0.8,
                "top_k": 20,
                "num_ctx": 2048,
                "num_predict": self.num_predict,
            },
        )
        return self._normalize_model_payload(model_payload, user_text)

    def _normalize_model_payload(
        self,
        model_payload: dict[str, Any],
        source_text: str = "",
    ) -> DescriptionOrganizationResult:
        status = str(model_payload.get("status", "")).strip()
        if status not in {"organized", "needs_clarification"}:
            status = "needs_clarification"

        organized_text = str(model_payload.get("organized_text", "")).strip()
        clarification_question = str(
            model_payload.get("clarification_question", "")
        ).strip()

        confidence = model_payload.get("confidence", 0.0)
        if not isinstance(confidence, int | float):
            confidence = 0.0
        confidence = max(0.0, min(float(confidence), 1.0))

        if status == "organized" and not organized_text:
            status = "needs_clarification"
        if len(organized_text) > self.max_output_chars:
            status = "needs_clarification"
            organized_text = ""
            clarification_question = (
                "A IA local gerou uma resposta maior que o permitido. "
                "Pode resumir o problema em uma frase?"
            )
        if status == "organized" and self._organized_text_looks_unsafe(
            organized_text,
            source_text,
        ):
            status = "needs_clarification"
            organized_text = ""
            clarification_question = (
                "Não consegui organizar a descrição com segurança. "
                "Pode explicar novamente o problema ou solicitação?"
            )
        if status == "needs_clarification" and not clarification_question:
            clarification_question = (
                "Não entendi bem a descrição. Pode explicar novamente o que precisa?"
            )

        return DescriptionOrganizationResult(
            status=status,
            organized_text=organized_text,
            clarification_question=clarification_question,
            confidence=confidence,
            backend=self.backend_name,
        )

    @staticmethod
    def _organized_text_looks_unsafe(
        organized_text: str,
        source_text: str = "",
    ) -> bool:
        normalized = GenerativeDescriptionOrganizer._normalize_text(organized_text)
        normalized_source = GenerativeDescriptionOrganizer._normalize_text(source_text)
        unsafe_fragments = (
            "nao foi identificado",
            "não foi identificado",
            "nao identificado",
            "não identificado",
            "foi identificado",
            "identificado e resolvido",
            "nao foi informado",
            "não foi informado",
            "nao foi inclus",
            "não foi inclus",
            "nao foi possivel identificar",
            "não foi possível identificar",
            "foi resolvido",
            "foi causada",
            "foi causado",
            "é causada",
            "é causado",
            "e causada",
            "e causado",
            "causado por",
            "causada por",
            "causa provável",
            "provavelmente",
            "pode indicar",
            "pode ser",
            "talvez",
            "sugere ",
            "sugerindo",
            "indicando",
            "deve ser",
            "realize ",
            "para o equipamento",
        )
        if any(fragment in normalized for fragment in unsafe_fragments):
            return True

        unsupported_terms = (
            "categoria",
            "sistema",
            "interface",
            "configurado",
            "funcionamento",
            "ativo",
            "falha tecnica",
            "falhas tecnicas",
        )
        return any(
            term in normalized and term not in normalized_source
            for term in unsupported_terms
        )

    @staticmethod
    def _normalize_text(text: str) -> str:
        normalized = unicodedata.normalize("NFKD", text.casefold())
        normalized = "".join(
            char for char in normalized if not unicodedata.combining(char)
        )
        return re.sub(r"\s+", " ", normalized).strip()

    @staticmethod
    def _build_system_prompt() -> str:
        return (
            "Você é uma IA local generativa usada exclusivamente para organizar "
            "descrições curtas de chamados de TI em português do Brasil.\n\n"
            "Tarefa única: transformar o texto bruto do usuário em UMA frase curta "
            "de chamado, preservando a intenção original.\n\n"
            "Regras obrigatórias:\n"
            "1. Responda somente JSON válido.\n"
            "2. Não converse com o usuário fora do JSON.\n"
            "3. Preserve a voz do solicitante: normalmente comece com 'Estou', "
            "'Preciso', 'Não consigo', 'Solicito' ou verbo equivalente ao original.\n"
            "4. Não transforme pedido em ordem. Nunca comece com 'Realize'.\n"
            "5. Não invente diagnóstico, causa, solução, sistema, equipamento, "
            "usuário, setor, status ou gravidade.\n"
            "6. Não diga que algo 'não foi identificado'. Isso é proibido.\n"
            "7. Não negue o relato do usuário. Apenas organize o que ele disse.\n"
            "8. Se o usuário informou 'problema grave', preserve isso como relato, "
            "sem calcular gravidade.\n"
            "9. Corrija erros óbvios de digitação apenas quando a correção for "
            "muito segura pelo contexto.\n"
            "10. Se não for seguro corrigir, retorne needs_clarification.\n\n"
            "Exemplos corretos:\n"
            "Entrada: Estou com problema grave no meu desktop\n"
            "Saída: {\"status\":\"organized\",\"organized_text\":\"Estou com um problema grave no meu desktop.\",\"clarification_question\":\"\",\"confidence\":0.9}\n"
            "Entrada: Preciso realizar um desktopi nov para mim\n"
            "Saída: {\"status\":\"organized\",\"organized_text\":\"Preciso solicitar um desktop novo para mim.\",\"clarification_question\":\"\",\"confidence\":0.78}\n"
            "Entrada: não consigo abrir e-mail\n"
            "Saída: {\"status\":\"organized\",\"organized_text\":\"Não consigo abrir o e-mail.\",\"clarification_question\":\"\",\"confidence\":0.88}\n"
            "Entrada: negocio la tela coisa ruim\n"
            "Saída: {\"status\":\"needs_clarification\",\"organized_text\":\"\",\"clarification_question\":\"Pode explicar melhor qual sistema, equipamento ou erro está com problema?\",\"confidence\":0.25}\n\n"
            "Exemplos proibidos:\n"
            "- 'Seu problema não foi identificado.'\n"
            "- 'Realize um desktop novo.'\n"
            "- 'O problema provavelmente é rede.'\n\n"
            "O JSON deve ter exatamente as chaves: status, organized_text, "
            "clarification_question, confidence."
        )

    @staticmethod
    def _build_user_prompt(
        user_text: str,
        category_name: str | None,
        purpose: str,
    ) -> str:
        return (
            f"Texto original do usuário: {user_text}\n\n"
            "Organize somente o texto original. Não mencione estado do fluxo, "
            "perguntas internas ou dados ausentes.\n"
            "Se o texto já estiver claro, apenas corrija pontuação e pequenos erros.\n\n"
            "Retorne JSON neste formato exato:\n"
            "{\n"
            '  "status": "organized" ou "needs_clarification",\n'
            '  "organized_text": "texto curto organizado ou vazio",\n'
            '  "clarification_question": "pergunta curta ou vazio",\n'
            '  "confidence": 0.0\n'
            "}"
        )


def build_generative_description_organizer(
    settings: AppSettings,
) -> GenerativeDescriptionOrganizer:
    if settings.local_light_ai_mode.casefold() == "mock":
        client = MockLocalGenerativeClient()
        backend_name = "mock-local-ai"
    else:
        client = OllamaLocalGenerativeClient(
            base_url=settings.ollama_base_url,
            model=settings.local_generative_model,
            timeout_seconds=settings.local_generative_timeout_seconds,
        )
        backend_name = f"ollama:{settings.local_generative_model}"

    return GenerativeDescriptionOrganizer(
        client=client,
        backend_name=backend_name,
        max_input_chars=settings.ai_max_input_chars,
        max_output_chars=settings.ai_max_output_chars,
        num_predict=settings.ai_ollama_num_predict,
        temperature=settings.ai_ollama_temperature,
    )
