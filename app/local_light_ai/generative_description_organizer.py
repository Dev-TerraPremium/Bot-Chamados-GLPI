import json
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
                "Nao foi possivel acionar a IA generativa local via Ollama."
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
    """Local generative organizer for ticket descriptions.

    The model is constrained to one task: produce a concise organized
    description or ask for clarification when the input is too broken.
    """

    def __init__(
        self,
        client: LocalGenerativeClient,
        backend_name: str,
    ) -> None:
        self.client = client
        self.backend_name = backend_name

    def organize_ticket_description(
        self,
        user_text: str,
        category_name: str | None = None,
        purpose: str = "descricao_chamado",
    ) -> DescriptionOrganizationResult:
        model_payload = self.client.generate_json(
            system_prompt=self._build_system_prompt(),
            user_prompt=self._build_user_prompt(user_text, category_name, purpose),
            options={
                "temperature": 0.1,
                "top_p": 0.8,
                "top_k": 20,
                "num_ctx": 2048,
                "num_predict": 180,
            },
        )
        return self._normalize_model_payload(model_payload)

    def _normalize_model_payload(
        self, model_payload: dict[str, Any]
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
        if status == "organized" and self._organized_text_looks_unsafe(
            organized_text
        ):
            status = "needs_clarification"
            organized_text = ""
            clarification_question = (
                "Nao consegui organizar a descricao com seguranca. "
                "Pode explicar novamente o problema ou solicitacao?"
            )
        if status == "needs_clarification" and not clarification_question:
            clarification_question = (
                "Nao entendi bem a descricao. Pode explicar novamente o que precisa?"
            )

        return DescriptionOrganizationResult(
            status=status,
            organized_text=organized_text,
            clarification_question=clarification_question,
            confidence=confidence,
            backend=self.backend_name,
        )

    @staticmethod
    def _organized_text_looks_unsafe(organized_text: str) -> bool:
        normalized = organized_text.casefold()
        unsafe_fragments = (
            "nao foi identificado",
            "não foi identificado",
            "nao identificado",
            "não identificado",
            "nao foi possivel identificar",
            "não foi possível identificar",
            "causa provável",
            "provavelmente",
            "deve ser",
            "realize ",
            "para o equipamento",
        )
        return any(fragment in normalized for fragment in unsafe_fragments)

    @staticmethod
    def _build_system_prompt() -> str:
        return (
            "Voce e uma IA local generativa usada exclusivamente para organizar "
            "descricoes curtas de chamados de TI em portugues do Brasil.\n\n"
            "Tarefa unica: transformar o texto bruto do usuario em UMA frase curta "
            "de chamado, preservando a intencao original.\n\n"
            "Regras obrigatorias:\n"
            "1. Responda somente JSON valido.\n"
            "2. Nao converse com o usuario fora do JSON.\n"
            "3. Preserve a voz do solicitante: normalmente comece com 'Estou', "
            "'Preciso', 'Nao consigo', 'Solicito' ou verbo equivalente ao original.\n"
            "4. Nao transforme pedido em ordem. Nunca comece com 'Realize'.\n"
            "5. Nao invente diagnostico, causa, solucao, sistema, equipamento, "
            "usuario, setor, status ou gravidade.\n"
            "6. Nao diga que algo 'nao foi identificado'. Isso e proibido.\n"
            "7. Nao negue o relato do usuario. Apenas organize o que ele disse.\n"
            "8. Se o usuario informou 'problema grave', preserve isso como relato, "
            "sem calcular gravidade.\n"
            "9. Corrija erros obvios de digitacao apenas quando a correcao for "
            "muito segura pelo contexto.\n"
            "10. Se nao for seguro corrigir, retorne needs_clarification.\n\n"
            "Exemplos corretos:\n"
            "Entrada: Estou com problema grave no meu desktop\n"
            "Saida: {\"status\":\"organized\",\"organized_text\":\"Estou com um problema grave no meu desktop.\",\"clarification_question\":\"\",\"confidence\":0.9}\n"
            "Entrada: Preciso realizar um desktopi nov para mim\n"
            "Saida: {\"status\":\"organized\",\"organized_text\":\"Preciso solicitar um desktop novo para mim.\",\"clarification_question\":\"\",\"confidence\":0.78}\n"
            "Entrada: nao consigo abrir email\n"
            "Saida: {\"status\":\"organized\",\"organized_text\":\"Nao consigo abrir o e-mail.\",\"clarification_question\":\"\",\"confidence\":0.88}\n"
            "Entrada: negocio la tela coisa ruim\n"
            "Saida: {\"status\":\"needs_clarification\",\"organized_text\":\"\",\"clarification_question\":\"Pode explicar melhor qual sistema, equipamento ou erro esta com problema?\",\"confidence\":0.25}\n\n"
            "Exemplos proibidos:\n"
            "- 'Seu problema nao foi identificado.'\n"
            "- 'Realize um desktop novo.'\n"
            "- 'O problema provavelmente e rede.'\n\n"
            "O JSON deve ter exatamente as chaves: status, organized_text, "
            "clarification_question, confidence."
        )

    @staticmethod
    def _build_user_prompt(
        user_text: str,
        category_name: str | None,
        purpose: str,
    ) -> str:
        category = category_name or "Nao informada"
        return (
            f"Finalidade: {purpose}\n"
            f"Categoria informada pelo fluxo: {category}\n"
            f"Texto original do usuario: {user_text}\n\n"
            "Organize somente o texto original. Use a categoria apenas como contexto "
            "leve para entender termos, nao para inventar informacoes.\n"
            "Se o texto ja estiver claro, apenas corrija pontuacao e pequenos erros.\n\n"
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
    client = OllamaLocalGenerativeClient(
        base_url=settings.ollama_base_url,
        model=settings.local_generative_model,
        timeout_seconds=settings.local_generative_timeout_seconds,
    )
    return GenerativeDescriptionOrganizer(
        client=client,
        backend_name=f"ollama:{settings.local_generative_model}",
    )
