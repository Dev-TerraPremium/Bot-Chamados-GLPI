import re
import unicodedata
from typing import Any

from app.application_config.settings import AppSettings
from app.local_light_ai.description_organization_models import (
    GuidedDetailingResult,
    LocalGenerativeAIUnavailableError,
)
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
        del category_name
        turns = self._normalize_turns(clarification_turns, max_questions)
        context_text = self._build_context_text(original_description, turns)

        if len(turns) >= max_questions:
            return self._ready_result(original_description, turns, confidence=0.68)

        if len(context_text) > self.max_input_chars:
            return self._ready_result(original_description, turns, confidence=0.58)

        if self._can_finalize_without_model(original_description, turns):
            return self._ready_result(original_description, turns, confidence=0.78)

        model_payload = self.client.generate_json(
            system_prompt=self._build_system_prompt(),
            user_prompt=self._build_user_prompt(
                original_description,
                turns,
                max_questions,
            ),
            options={
                "temperature": self.temperature,
                "num_predict": min(self.num_predict, self.max_output_chars),
                "num_thread": self.num_thread,
                "purpose": "descricao_chamado_pergunta_guiada",
            },
        )
        if isinstance(model_payload, str):
            raise LocalGenerativeAIUnavailableError(
                "A IA generativa local retornou uma resposta fora do formato esperado."
            )
        return self._normalize_model_payload(
            model_payload,
            original_description,
            turns,
            max_questions,
        )

    def _normalize_model_payload(
        self,
        model_payload: dict[str, Any],
        original_description: str,
        clarification_turns: list[dict[str, str]],
        max_questions: int,
    ) -> GuidedDetailingResult:
        status = str(model_payload.get("status", "")).strip().casefold()
        if status not in {"ask_next", "ready"}:
            status = (
                "ask_next"
                if self._needs_more_triage(original_description, clarification_turns)
                else "ready"
            )

        next_question = str(model_payload.get("next_question", "")).strip()
        confidence = self._clamp_confidence(model_payload.get("confidence", 0.0))
        remaining_questions = max_questions - len(clarification_turns)

        if status == "ready" and remaining_questions > 0:
            missing_topic = self._infer_missing_topic(
                original_description,
                clarification_turns,
            )
            if missing_topic is not None:
                return self._fallback_or_ready(
                    original_description,
                    clarification_turns,
                    confidence=min(confidence or 0.55, 0.55),
                    force_topic=missing_topic,
                )

        if status == "ask_next" and remaining_questions <= 0:
            status = "ready"

        if status == "ask_next":
            next_question = self._normalize_question(next_question)
            if not self._question_is_allowed(next_question, clarification_turns):
                fallback_question = self._fallback_question(
                    original_description,
                    clarification_turns,
                )
                if fallback_question:
                    return self._ask_result(
                        fallback_question,
                        confidence=min(confidence or 0.5, 0.5),
                        backend="local-guided-question",
                    )
                return self._ready_result(
                    original_description,
                    clarification_turns,
                    confidence=min(confidence or 0.5, 0.5),
                )
            return self._ask_result(
                next_question,
                confidence=max(confidence, 0.45),
                backend=self.backend_name,
            )

        return self._ready_result(
            original_description,
            clarification_turns,
            confidence=max(confidence, 0.6),
        )

    def _ask_result(
        self,
        question: str,
        *,
        confidence: float,
        backend: str,
    ) -> GuidedDetailingResult:
        return GuidedDetailingResult(
            status="ask_next",
            next_question=question,
            organized_text="",
            confidence=confidence,
            backend=backend,
        )

    def _fallback_or_ready(
        self,
        original_description: str,
        clarification_turns: list[dict[str, str]],
        *,
        confidence: float,
        force_topic: str | None = None,
    ) -> GuidedDetailingResult:
        fallback_question = self._fallback_question(
            original_description,
            clarification_turns,
            force_topic=force_topic,
        )
        if fallback_question:
            return self._ask_result(
                fallback_question,
                confidence=confidence,
                backend="local-guided-question",
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
        *,
        force_topic: str | None = None,
    ) -> str:
        topic = force_topic or self._infer_missing_topic(
            original_description,
            clarification_turns,
        )
        normalized = self._normalize_text(
            self._build_compact_summary(original_description, clarification_turns)
        )

        topic_candidates: dict[str, list[str]] = {
            "affected_item": [
                "Poderia me detalhar qual item, sistema, equipamento ou processo está sendo afetado?",
            ],
            "observed_behavior": [
                "Poderia me detalhar o que está acontecendo exatamente e qual comportamento você percebe?",
                "Qual erro aparece ou o que acontece exatamente quando você tenta usar isso?",
            ],
            "specific_application": [
                "Qual aplicativo, sistema ou funcionalidade exatamente está apresentando esse comportamento?",
                "Qual aplicativo ou sistema exatamente está falhando?",
            ],
            "request_goal": [
                "O que você precisa exatamente: acesso, instalação, ajuste, troca ou algo novo?",
            ],
        }
        ordered_topics = (
            [topic] if topic else []
        ) + [
            "observed_behavior",
            "affected_item",
            "specific_application",
            "request_goal",
        ]
        seen_topics: set[str] = set()
        for candidate_topic in ordered_topics:
            if not candidate_topic or candidate_topic in seen_topics:
                continue
            seen_topics.add(candidate_topic)
            for candidate in topic_candidates.get(candidate_topic, []):
                if self._question_is_allowed(candidate, clarification_turns):
                    return candidate
        return ""

    def _can_finalize_without_model(
        self,
        original_description: str,
        clarification_turns: list[dict[str, str]],
    ) -> bool:
        if clarification_turns and not self._needs_more_triage(
            original_description,
            clarification_turns,
        ):
            return True
        return not clarification_turns and self._looks_clear_request(original_description)

    def _needs_more_triage(
        self,
        original_description: str,
        clarification_turns: list[dict[str, str]],
    ) -> bool:
        return self._infer_missing_topic(original_description, clarification_turns) is not None

    def _infer_missing_topic(
        self,
        original_description: str,
        clarification_turns: list[dict[str, str]],
    ) -> str | None:
        if len(clarification_turns) >= 5:
            return None

        combined_text = self._build_compact_summary(
            original_description,
            clarification_turns,
        )
        normalized = self._normalize_text(combined_text)
        if not normalized:
            return "observed_behavior"

        if self._looks_clear_request(combined_text):
            return None

        if not self._has_affected_target(normalized):
            return "affected_item"

        if not self._has_observed_behavior(normalized):
            return "observed_behavior"

        if self._needs_specific_application_detail(normalized):
            return "specific_application"

        if not clarification_turns and self._looks_too_vague(original_description):
            return "observed_behavior"

        return None

    def _looks_clear_request(self, text: str) -> bool:
        normalized = self._normalize_text(text)
        clear_request_patterns = (
            r"\bsolicito\b",
            r"\bpreciso de acesso\b",
            r"\bpreciso que instale\b",
            r"\bpreciso instalar\b",
            r"\bpreciso trocar\b",
            r"\bpreciso liberar\b",
            r"\bpreciso criar\b",
            r"\bgostaria de solicitar\b",
            r"\bcompra\b",
            r"\baquisicao\b",
        )
        return any(re.search(pattern, normalized) for pattern in clear_request_patterns)

    def _has_affected_target(self, normalized_text: str) -> bool:
        target_keywords = (
            "computador",
            "notebook",
            "pc",
            "celular",
            "smartphone",
            "telefone",
            "ramal",
            "impressora",
            "wifi",
            "rede",
            "internet",
            "vpn",
            "email",
            "outlook",
            "teams",
            "excel",
            "word",
            "erp",
            "solution",
            "sistema",
            "aplicativo",
            "app",
            "programa",
            "portal",
            "acesso",
            "login",
            "usuario",
            "senha",
            "arquivo",
            "pasta",
            "nota",
            "nfe",
            "nfse",
            "camera",
            "cftv",
        )
        if any(keyword in normalized_text for keyword in target_keywords):
            return True
        return bool(
            re.search(
                r"\b(no|na|nos|nas|do|da|dos|das|com|em)\s+[a-z0-9_-]{3,}",
                normalized_text,
            )
        )

    def _has_observed_behavior(self, normalized_text: str) -> bool:
        behavior_patterns = (
            r"\bnao\b.*\b(abre|acessa|entra|carrega|funciona|imprime|liga|salva|envia)\b",
            r"\b(fecha|trav(a|ando)|cai|caindo|lento|bloquead[oa]|sem acesso|desconecta)\b",
            r"\b(aparece|mostra|exibe)\b.*\b(erro|mensagem|codigo)\b",
            r"\b(tela azul|erro|mensagem|falha|instabilidade)\b",
            r"\b(intermitente|constante|toda hora|toda vez|ao abrir|ao acessar|ao iniciar)\b",
        )
        return any(re.search(pattern, normalized_text) for pattern in behavior_patterns)

    def _has_time_or_frequency_detail(self, normalized_text: str) -> bool:
        markers = (
            "desde",
            "hoje",
            "ontem",
            "agora",
            "ao abrir",
            "ao acessar",
            "ao iniciar",
            "sempre",
            "as vezes",
            "intermitente",
            "constante",
            "toda hora",
            "toda vez",
        )
        return any(marker in normalized_text for marker in markers)

    def _needs_specific_application_detail(self, normalized_text: str) -> bool:
        if not any(
            word in normalized_text
            for word in ("aplicativo", "app", "sistema", "programa")
        ):
            return False
        if not self._has_observed_behavior(normalized_text):
            return False
        if any(
            word in normalized_text
            for word in (
                "outlook",
                "teams",
                "whatsapp",
                "excel",
                "word",
                "solution",
                "chrome",
                "edge",
                "firefox",
                "erp",
                "glpi",
                "financeiro",
                "fiscal",
                "comercial",
                "rh",
            )
        ):
            return False
        if re.search(
            r"\b(um|uma|o|a)\s+(aplicativo|app|sistema|programa)\b",
            normalized_text,
        ):
            return True
        if re.search(
            r"\b(no|na|em)\s+(aplicativo|app|sistema|programa)\b",
            normalized_text,
        ):
            return True
        if any(word in normalized_text for word in ("aplicativo", "app")):
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
        if not isinstance(value, (int, float)):
            return 0.0
        return max(0.0, min(float(value), 1.0))

    @staticmethod
    def _build_system_prompt() -> str:
        return (
            "Voce atua como um analista de TI experiente abrindo chamados em portugues do Brasil.\n"
            "Seu unico objetivo e complementar o relato do usuario com o minimo de perguntas necessario.\n"
            "Use a memoria curta da conversa para nao repetir o que ja foi dito.\n"
            "Pergunte somente quando faltar informacao relevante para o tecnico entender o problema ou pedido.\n"
            "Faca no maximo uma pergunta por resposta, de forma natural, objetiva e contextual.\n"
            "Nao transforme a conversa em formulario, nao enumere multiplas perguntas e nao invente causa, impacto, solucao ou sistema.\n"
            "Nao peca senha, token, codigo de verificacao, CPF ou qualquer dado sensivel.\n"
            "Se ja houver contexto suficiente para abrir o chamado, retorne ready.\n"
            "Responda somente JSON com: status, next_question, confidence."
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
            f"Historico curto da conversa:\n{history}\n\n"
            "Pense como analista: identifique a unica lacuna mais importante para o chamado final.\n"
            "Se ainda faltar contexto relevante, use ask_next com uma pergunta natural e especifica.\n"
            "Se ja estiver suficiente para abrir o chamado sem perder contexto importante, use ready.\n"
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
        self.num_thread = 1
        self.temperature = 0.1

    def detail_ticket_description(
        self,
        original_description: str,
        clarification_turns: list[dict[str, str]],
        category_name: str | None,
        max_questions: int,
    ) -> GuidedDetailingResult:
        del category_name
        turns = self._normalize_turns(clarification_turns, max_questions)
        if len(turns) >= max_questions or not self._needs_more_triage(
            original_description,
            turns,
        ):
            return self._ready_result(original_description, turns, confidence=0.95)
        return self._ask_result(
            self._fallback_question(original_description, turns),
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
