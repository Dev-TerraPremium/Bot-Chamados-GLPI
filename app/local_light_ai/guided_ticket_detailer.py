import re
import unicodedata
from typing import Any

from app.application_config.settings import AppSettings
from app.local_light_ai.description_organization_models import GuidedDetailingResult
from app.local_light_ai.generative_description_organizer import (
    LocalGenerativeClient,
    build_local_generative_client,
)


class GuidedTicketDetailer:
    """Local guided interviewer for ticket-opening descriptions."""

    def __init__(
        self,
        client: LocalGenerativeClient,
        backend_name: str,
        max_input_chars: int = 1000,
        max_output_chars: int = 800,
        max_question_chars: int = 180,
        num_predict: int = 180,
        num_thread: int = 4,
        temperature: float = 0.1,
    ) -> None:
        self.client = client
        self.backend_name = backend_name
        self.max_input_chars = max_input_chars
        self.max_output_chars = max_output_chars
        self.max_question_chars = max_question_chars
        self.num_predict = num_predict
        self.num_thread = max(1, num_thread)
        self.temperature = temperature

    def detail_ticket_description(
        self,
        original_description: str,
        clarification_turns: list[dict[str, str]],
        category_name: str | None,
        max_questions: int,
    ) -> GuidedDetailingResult:
        turns = self._normalize_turns(clarification_turns, max_questions)
        if len(turns) >= max_questions:
            return self._ready_result(original_description, turns, confidence=0.65)

        if len(self._build_context_text(original_description, turns)) > self.max_input_chars:
            return self._ready_result(original_description, turns, confidence=0.55)

        if not turns and self._needs_more_triage(original_description, turns):
            return GuidedDetailingResult(
                status="ask_next",
                next_question=self._fallback_question(original_description, turns),
                organized_text="",
                confidence=0.75,
                backend="local-guided-question",
            )

        if turns or not self._needs_more_triage(original_description, turns):
            return self._ready_result(original_description, turns, confidence=0.72)

        return self._ready_result(original_description, turns, confidence=0.65)

    def _normalize_model_payload(
        self,
        model_payload: dict[str, Any],
        original_description: str,
        clarification_turns: list[dict[str, str]],
        max_questions: int,
    ) -> GuidedDetailingResult:
        status = str(model_payload.get("status", "")).strip()
        if status not in {"ask_next", "ready"}:
            status = (
                "ask_next"
                if self._needs_more_triage(original_description, clarification_turns)
                else "ready"
            )

        next_question = str(model_payload.get("next_question", "")).strip()
        confidence = self._clamp_confidence(model_payload.get("confidence", 0.0))

        remaining_questions = max_questions - len(clarification_turns)
        if (
            status == "ready"
            and remaining_questions > 0
            and self._needs_more_triage(original_description, clarification_turns)
        ):
            status = "ask_next"
            next_question = self._fallback_question(
                original_description,
                clarification_turns,
            )
            confidence = min(confidence, 0.55)

        if status == "ask_next" and remaining_questions <= 0:
            status = "ready"

        if status == "ask_next":
            next_question = self._normalize_question(next_question)
            if not self._question_is_allowed(next_question, clarification_turns):
                next_question = self._fallback_question(
                    original_description,
                    clarification_turns,
                )
                confidence = min(confidence, 0.5)
            if not next_question:
                return self._ready_result(
                    original_description,
                    clarification_turns,
                    confidence=min(confidence, 0.5),
                )
            return GuidedDetailingResult(
                status="ask_next",
                next_question=next_question,
                organized_text="",
                confidence=confidence,
                backend=self.backend_name,
            )

        return self._ready_result(
            original_description,
            clarification_turns,
            confidence=confidence,
        )

    def _ready_result(
        self,
        original_description: str,
        clarification_turns: list[dict[str, str]],
        confidence: float,
    ) -> GuidedDetailingResult:
        return GuidedDetailingResult(
            status="ready",
            next_question="",
            organized_text=self._build_compact_summary(
                original_description,
                clarification_turns,
            ),
            confidence=confidence,
            backend=self.backend_name,
        )

    def _normalize_question(self, question: str) -> str:
        question = " ".join(question.split())
        if len(question) > self.max_question_chars:
            return ""
        if question and not question.endswith("?"):
            question += "?"
        return question

    def _question_is_allowed(
        self,
        question: str,
        clarification_turns: list[dict[str, str]],
    ) -> bool:
        if not question:
            return False
        normalized = self._normalize_text(question)
        if self._question_was_already_asked(normalized, clarification_turns):
            return False

        unsafe_patterns = (
            r"\bsua senha\b",
            r"\bsenha atual\b",
            r"\binforme .*senha\b",
            r"\btoken\b",
            r"codigo de verificacao",
            r"\bcpf\b",
            r"\brg\b",
            r"cartao",
            r"\bexecute\b",
            r"\bpowershell\b",
            r"\bcmd\b",
            r"\bsudo\b",
            r"\bformat(ar)?\b",
            r"\bapagar\b",
            r"\bdeletar\b",
            r"causa provavel",
            r"\bprovavelmente\b",
        )
        return not any(re.search(pattern, normalized) for pattern in unsafe_patterns)

    def _question_was_already_asked(
        self,
        normalized_question: str,
        clarification_turns: list[dict[str, str]],
    ) -> bool:
        asked_questions = {
            self._normalize_text(turn.get("question", ""))
            for turn in clarification_turns
        }
        return normalized_question in asked_questions

    def _fallback_question(
        self,
        original_description: str,
        clarification_turns: list[dict[str, str]],
    ) -> str:
        candidates = [
            "Qual item, sistema, processo ou servico esta afetado e o que acontece exatamente?",
            "Qual erro aparece ou qual comportamento voce percebe exatamente?",
            "Esse pedido e para corrigir algo que falhou, substituir algo existente ou atender uma nova necessidade?",
            "Desde quando isso acontece e e constante ou intermitente?",
            "Isso afeta somente voce ou tambem outras pessoas/setores?",
            "Qual setor ou localidade esta relacionado ao chamado?",
        ]
        for candidate in candidates:
            if self._question_is_allowed(candidate, clarification_turns):
                return candidate
        return ""

    def _needs_more_triage(
        self,
        original_description: str,
        clarification_turns: list[dict[str, str]],
    ) -> bool:
        if len(clarification_turns) >= 5:
            return False
        if not clarification_turns and self._looks_too_vague(original_description):
            return True
        return False

    def _looks_too_vague(self, original_description: str) -> bool:
        normalized = self._normalize_text(original_description)
        vague_fragments = (
            "problema de",
            "problema do",
            "problema da",
            "problema no",
            "problema na",
            "problema com",
            "problema em",
            "problema no computador",
            "problema no meu computador",
            "problema no pc",
            "erro de",
            "erro do",
            "erro da",
            "erro no",
            "erro na",
            "erro com",
            "erro em",
            "dificuldade de",
            "dificuldade do",
            "dificuldade da",
            "dificuldade no",
            "dificuldade na",
            "dificuldade com",
            "nao funciona",
            "nao consigo",
            "deu problema",
            "esta ruim",
        )
        detail_markers = (
            "quando",
            "ao ",
            "aparece",
            "mensagem",
            "erro ",
            "tela",
            "salvar",
            "emitir",
            "abrir",
            "acessar",
            "imprimir",
            "iniciar",
            "travando",
            "caindo",
            "lento",
            "bloqueado",
            "sem ",
        )
        word_count = len(normalized.split())
        has_vague_fragment = any(fragment in normalized for fragment in vague_fragments)
        has_generic_issue_pattern = bool(
            re.search(
                r"\b(problema|erro|dificuldade)(?:\s+\w+){0,3}\s+"
                r"(de|do|da|dos|das|no|na|nos|nas|com|em)\b",
                normalized,
            )
        )
        has_detail_marker = any(marker in normalized for marker in detail_markers)
        return word_count < 4 or (
            (has_vague_fragment or has_generic_issue_pattern)
            and not has_detail_marker
        )

    def _build_context_text(
        self,
        original_description: str,
        clarification_turns: list[dict[str, str]],
    ) -> str:
        lines = [original_description]
        for turn in clarification_turns:
            lines.append(turn.get("question", ""))
            lines.append(turn.get("answer", ""))
        return "\n".join(lines)

    def _build_compact_summary(
        self,
        original_description: str,
        clarification_turns: list[dict[str, str]],
    ) -> str:
        parts = [original_description.strip()]
        for turn in clarification_turns:
            answer = turn.get("answer", "").strip()
            if answer:
                parts.append(answer)
        compact_text = " ".join(part.strip(" .") for part in parts if part.strip())
        if compact_text and not compact_text.endswith((".", "!", "?")):
            compact_text += "."
        return compact_text

    def _normalize_turns(
        self,
        clarification_turns: list[dict[str, str]],
        max_questions: int,
    ) -> list[dict[str, str]]:
        normalized_turns = []
        for turn in clarification_turns[:max_questions]:
            question = " ".join(str(turn.get("question", "")).split())
            answer = " ".join(str(turn.get("answer", "")).split())
            if question or answer:
                normalized_turns.append({"question": question, "answer": answer})
        return normalized_turns

    @staticmethod
    def _normalize_text(text: str) -> str:
        normalized = unicodedata.normalize("NFKD", text.casefold())
        normalized = "".join(
            char for char in normalized if not unicodedata.combining(char)
        )
        normalized = re.sub(r"[^\w\s]", " ", normalized)
        return re.sub(r"\s+", " ", normalized).strip()

    @staticmethod
    def _clamp_confidence(value: Any) -> float:
        if not isinstance(value, int | float):
            return 0.0
        return max(0.0, min(float(value), 1.0))

    @staticmethod
    def _build_system_prompt() -> str:
        return (
            "Voce faz entrevista curta para abrir chamados de TI em portugues do Brasil.\n"
            "Responda somente JSON com: status, next_question, confidence.\n"
            "Use ask_next para fazer uma unica pergunta objetiva e util.\n"
            "Use ready somente quando ja houver detalhe suficiente para o atendimento entender o pedido ou problema.\n"
            "Nao repita pergunta, nao invente causa, sistema, local, gravidade ou solucao e nao peca dado sensivel."
        )

    @staticmethod
    def _build_user_prompt(
        original_description: str,
        clarification_turns: list[dict[str, str]],
        max_questions: int,
    ) -> str:
        history_lines = []
        for index, turn in enumerate(clarification_turns, start=1):
            history_lines.append(
                f"{index}. Pergunta: {turn.get('question', '')}\n"
                f"   Resposta: {turn.get('answer', '')}"
            )
        history = "\n".join(history_lines) or "Sem perguntas anteriores."
        remaining = max_questions - len(clarification_turns)
        return (
            f"Limite total de perguntas: {max_questions}\n"
            f"Perguntas restantes: {remaining}\n\n"
            f"Descricao inicial do usuario:\n{original_description}\n\n"
            f"Historico curto:\n{history}\n\n"
            "Decida o proximo passo com base na qualidade do chamado final, nao apenas na frase inicial.\n"
            "Se perguntar, faca somente uma pergunta util e contextual. Se ja houver informacao suficiente, use ready.\n"
            "Retorne JSON neste formato:\n"
            "{\n"
            '  "status": "ask_next" ou "ready",\n'
            '  "next_question": "pergunta curta ou vazio",\n'
            '  "confidence": 0.0\n'
            "}"
        )


class MockGuidedTicketDetailer(GuidedTicketDetailer):
    def __init__(self, backend_name: str = "mock-local-ai") -> None:
        self.backend_name = backend_name
        self.max_input_chars = 1000
        self.max_output_chars = 800
        self.max_question_chars = 180
        self.num_predict = 180
        self.temperature = 0.1

    def detail_ticket_description(
        self,
        original_description: str,
        clarification_turns: list[dict[str, str]],
        category_name: str | None,
        max_questions: int,
    ) -> GuidedDetailingResult:
        turns = self._normalize_turns(clarification_turns, max_questions)
        if len(turns) >= max_questions or not self._needs_more_triage(
            original_description,
            turns,
        ):
            return self._ready_result(original_description, turns, confidence=0.95)
        return GuidedDetailingResult(
            status="ask_next",
            next_question=self._fallback_question(original_description, turns),
            organized_text="",
            confidence=0.85,
            backend=self.backend_name,
        )


def build_guided_ticket_detailer(settings: AppSettings) -> GuidedTicketDetailer:
    if settings.local_light_ai_mode.casefold() == "mock":
        return MockGuidedTicketDetailer()

    client, backend_name = build_local_generative_client(settings)
    return GuidedTicketDetailer(
        client=client,
        backend_name=backend_name,
        max_input_chars=settings.ai_max_input_chars,
        max_output_chars=settings.ai_max_output_chars,
        num_predict=settings.ai_ollama_num_predict,
        num_thread=settings.ai_ollama_num_thread,
        temperature=settings.ai_ollama_temperature,
    )
