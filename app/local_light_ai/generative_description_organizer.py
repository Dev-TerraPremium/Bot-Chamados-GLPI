import json
import logging
import re
import time
import unicodedata
from typing import Any, Protocol

import httpx

from app.application_config.settings import AppSettings
from app.local_light_ai.description_organization_models import (
    DescriptionOrganizationResult,
    LocalGenerativeAIUnavailableError,
)


logger = logging.getLogger(__name__)


class LocalGenerativeClient(Protocol):
    def generate_json(
        self,
        system_prompt: str,
        user_prompt: str,
        options: dict[str, Any],
    ) -> dict[str, Any]:
        pass


class GoogleAIRateLimiter:
    def __init__(
        self,
        redis_url: str,
        *,
        rpm_limit: int,
        rpd_limit: int,
        enabled: bool = True,
    ) -> None:
        self.rpm_limit = max(0, rpm_limit)
        self.rpd_limit = max(0, rpd_limit)
        self.enabled = enabled
        self.redis_client = None
        if not enabled:
            return
        try:
            import redis

            self.redis_client = redis.Redis.from_url(redis_url)
        except Exception:
            logger.warning("google_ai_rate_limiter_unavailable", exc_info=True)

    def allow_request(self) -> bool:
        if not self.enabled or self.redis_client is None:
            return True
        if self.rpm_limit <= 0 and self.rpd_limit <= 0:
            return True

        minute_key = time.strftime("google_ai_quota:rpm:%Y%m%d%H%M", time.gmtime())
        day_key = time.strftime("google_ai_quota:rpd:%Y%m%d", time.gmtime())
        try:
            pipe = self.redis_client.pipeline()
            pipe.incr(minute_key)
            pipe.expire(minute_key, 120)
            pipe.incr(day_key)
            pipe.expire(day_key, 172800)
            minute_count, _, day_count, _ = pipe.execute()
        except Exception:
            logger.warning("google_ai_rate_limit_check_failed", exc_info=True)
            return True

        over_rpm = self.rpm_limit > 0 and int(minute_count) > self.rpm_limit
        over_rpd = self.rpd_limit > 0 and int(day_count) > self.rpd_limit
        if over_rpm or over_rpd:
            logger.warning(
                "google_ai_rate_limit_exceeded",
                extra={
                    "google_ai_rpm_limit": self.rpm_limit,
                    "google_ai_rpd_limit": self.rpd_limit,
                    "google_ai_rpm_count": int(minute_count),
                    "google_ai_rpd_count": int(day_count),
                },
            )
            return False
        return True


class MockLocalGenerativeClient:
    def generate_json(
        self,
        system_prompt: str,
        user_prompt: str,
        options: dict[str, Any],
    ) -> dict[str, Any]:
        user_text_prefix = "Texto original do usuario:"
        user_text = user_prompt.split(user_text_prefix, maxsplit=1)[-1]
        user_text = user_text.split("\n\n", maxsplit=1)[0]
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


class GoogleAILocalGenerativeClient:
    def __init__(
        self,
        base_url: str,
        model: str,
        api_key: str,
        timeout_seconds: float,
        max_retries: int = 1,
        rate_limiter: GoogleAIRateLimiter | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.timeout_seconds = max(1.0, timeout_seconds)
        self.max_retries = max(0, max_retries)
        self.rate_limiter = rate_limiter

    def generate_json(
        self,
        system_prompt: str,
        user_prompt: str,
        options: dict[str, Any],
    ) -> dict[str, Any]:
        if not self.api_key:
            raise LocalGenerativeAIUnavailableError(
                "Google AI API key ausente."
            )
        if self.rate_limiter is not None and not self.rate_limiter.allow_request():
            raise LocalGenerativeAIUnavailableError(
                "Limite configurado de uso do Google AI atingido."
            )

        generation_config = {
            "temperature": options.get("temperature", 0.1),
            "topP": options.get("top_p", 0.8),
            "topK": options.get("top_k", 20),
            "maxOutputTokens": int(options.get("num_predict", 256)),
            "responseMimeType": "application/json",
        }
        payload = {
            "systemInstruction": {
                "parts": [{"text": system_prompt}],
            },
            "contents": [
                {
                    "parts": [{"text": user_prompt}],
                }
            ],
            "generationConfig": generation_config,
        }
        response = None
        last_error: Exception | None = None
        purpose = str(options.get("purpose") or "unknown")
        started_at = time.perf_counter()
        attempts_allowed = self.max_retries + 1
        for attempt in range(attempts_allowed):
            attempt_started_at = time.perf_counter()
            status_code = 0
            try:
                response = httpx.post(
                    f"{self.base_url}/models/{self.model}:generateContent",
                    headers={
                        "Content-Type": "application/json",
                        "X-goog-api-key": self.api_key,
                    },
                    json=payload,
                    timeout=self.timeout_seconds,
                )
                status_code = response.status_code
                response.raise_for_status()
                logger.info(
                    "google_ai_request_attempt",
                    extra={
                        "model": self.model,
                        "purpose": purpose,
                        "google_attempt": attempt + 1,
                        "google_attempts": attempt + 1,
                        "google_duration_ms": int(
                            (time.perf_counter() - attempt_started_at) * 1000
                        ),
                        "status_code": status_code,
                    },
                )
                break
            except httpx.HTTPStatusError as exc:
                response = exc.response
                status_code = response.status_code
                last_error = exc
                logger.warning(
                    "google_ai_request_attempt_failed",
                    extra={
                        "model": self.model,
                        "purpose": purpose,
                        "google_attempt": attempt + 1,
                        "google_attempts": attempt + 1,
                        "google_duration_ms": int(
                            (time.perf_counter() - attempt_started_at) * 1000
                        ),
                        "status_code": status_code,
                    },
                )
                if (
                    response.status_code not in {429, 500, 502, 503, 504}
                    or attempt >= self.max_retries
                ):
                    raise LocalGenerativeAIUnavailableError(
                        "Nao foi possivel acionar a IA generativa Google."
                    ) from exc
            except httpx.TimeoutException as exc:
                last_error = exc
                logger.warning(
                    "google_ai_request_attempt_failed",
                    extra={
                        "model": self.model,
                        "purpose": purpose,
                        "google_attempt": attempt + 1,
                        "google_attempts": attempt + 1,
                        "google_duration_ms": int(
                            (time.perf_counter() - attempt_started_at) * 1000
                        ),
                        "status_code": status_code,
                    },
                )
                raise LocalGenerativeAIUnavailableError(
                    "Nao foi possivel acionar a IA generativa Google."
                ) from exc
            except httpx.HTTPError as exc:
                last_error = exc
                logger.warning(
                    "google_ai_request_attempt_failed",
                    extra={
                        "model": self.model,
                        "purpose": purpose,
                        "google_attempt": attempt + 1,
                        "google_attempts": attempt + 1,
                        "google_duration_ms": int(
                            (time.perf_counter() - attempt_started_at) * 1000
                        ),
                        "status_code": status_code,
                    },
                )
                raise LocalGenerativeAIUnavailableError(
                    "Nao foi possivel acionar a IA generativa Google."
                ) from exc

        if response is None:
            raise LocalGenerativeAIUnavailableError(
                "Nao foi possivel acionar a IA generativa Google."
            ) from last_error

        try:
            response_payload = response.json()
            raw_response = (
                response_payload["candidates"][0]["content"]["parts"][0]["text"]
            )
            parsed_payload = json.loads(raw_response)
            if not isinstance(parsed_payload, dict):
                raise TypeError("Google AI JSON response must be an object.")
            parsed_payload["_usage_metadata"] = response_payload.get(
                "usageMetadata",
                {},
            )
            logger.info(
                "google_ai_request_completed",
                extra={
                    "model": self.model,
                    "purpose": purpose,
                    "google_attempts": attempt + 1,
                    "google_duration_ms": int((time.perf_counter() - started_at) * 1000),
                    "status_code": response.status_code,
                    "usageMetadata": response_payload.get("usageMetadata", {}),
                },
            )
            return parsed_payload
        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
            logger.warning(
                "google_ai_response_parse_failed",
                extra={
                    "model": self.model,
                    "purpose": purpose,
                    "google_attempts": attempt + 1,
                    "google_duration_ms": int((time.perf_counter() - started_at) * 1000),
                    "status_code": response.status_code,
                },
            )
            raise LocalGenerativeAIUnavailableError(
                "A IA generativa Google retornou uma resposta fora do formato esperado."
            ) from exc


def _bounded_ai_request_timeout(settings: AppSettings) -> float:
    # Keep the Ollama call below the Celery soft limit while honoring runtime config.
    return max(
        1.0,
        min(
            settings.local_generative_timeout_seconds,
            max(1, settings.ai_task_timeout_seconds - 1),
        ),
    )


def _bounded_google_request_timeout(settings: AppSettings) -> float:
    # Fail fast for production UX and keep the call below the Celery soft limit.
    return max(
        1.0,
        min(
            settings.google_ai_timeout_seconds,
            max(1, settings.ai_task_timeout_seconds - 1),
        ),
    )


def build_local_generative_client(
    settings: AppSettings,
) -> tuple[LocalGenerativeClient, str]:
    mode = settings.local_light_ai_mode.casefold()
    if mode == "mock":
        return MockLocalGenerativeClient(), "mock-local-ai"
    if mode == "generative_google":
        return (
            GoogleAILocalGenerativeClient(
                base_url=settings.google_ai_base_url,
                model=settings.google_ai_model,
                api_key=settings.google_ai_api_key,
                timeout_seconds=_bounded_google_request_timeout(settings),
                max_retries=settings.google_ai_max_retries,
                rate_limiter=GoogleAIRateLimiter(
                    settings.redis_url,
                    rpm_limit=settings.google_ai_rpm_limit,
                    rpd_limit=settings.google_ai_rpd_limit,
                    enabled=settings.google_ai_rate_limit_enabled,
                ),
            ),
            f"google:{settings.google_ai_model}",
        )
    if mode in {"generative_ollama", "ollama"}:
        if not settings.local_ollama_enabled:
            raise LocalGenerativeAIUnavailableError(
                "A IA local via Ollama esta desabilitada por configuracao."
            )
        return (
            OllamaLocalGenerativeClient(
                base_url=settings.ollama_base_url,
                model=settings.local_generative_model,
                timeout_seconds=_bounded_ai_request_timeout(settings),
            ),
            f"ollama:{settings.local_generative_model}",
        )
    raise LocalGenerativeAIUnavailableError(
        f"Modo de IA generativa nao suportado: {settings.local_light_ai_mode}."
    )


class GenerativeDescriptionOrganizer:
    """Local generative organizer for ticket descriptions."""

    def __init__(
        self,
        client: LocalGenerativeClient,
        backend_name: str,
        max_input_chars: int = 1000,
        max_output_chars: int = 800,
        num_predict: int = 180,
        num_thread: int = 4,
        temperature: float = 0.1,
    ) -> None:
        self.client = client
        self.backend_name = backend_name
        self.max_input_chars = max_input_chars
        self.max_output_chars = max_output_chars
        self.num_predict = num_predict
        self.num_thread = max(1, num_thread)
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
                "num_ctx": 512,
                "num_predict": self.num_predict,
                "num_thread": self.num_thread,
                "purpose": purpose,
            },
        )
        return self._normalize_model_payload(model_payload, user_text)

    def _normalize_model_payload(
        self,
        model_payload: dict[str, Any],
        source_text: str = "",
    ) -> DescriptionOrganizationResult:
        status = self._normalize_status(model_payload.get("status"))
        organized_text = str(model_payload.get("organized_text", "")).strip()
        clarification_question = str(
            model_payload.get("clarification_question", "")
        ).strip()
        confidence = self._normalize_confidence(model_payload.get("confidence", 0.0))

        if status == "needs_clarification" and organized_text and not clarification_question:
            status = "organized"

        if (
            status == "needs_clarification"
            and organized_text
            and len(self._normalize_text(source_text).split()) >= 5
        ):
            status = "organized"

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
            fallback_text = self._first_person_fallback_text(source_text)
            if fallback_text:
                organized_text = fallback_text
                clarification_question = ""
                confidence = min(confidence, 0.4)
            else:
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
            "nao identificado",
            "foi identificado",
            "identificado e resolvido",
            "nao foi informado",
            "nao foi inclus",
            "nao foi possivel identificar",
            "foi resolvido",
            "foi causada",
            "foi causado",
            "e causada",
            "e causado",
            "causado por",
            "causada por",
            "causa provavel",
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
            "o usuario",
            "a usuario",
            "usuario informou",
            "usuario reportou",
            "usuario relatou",
            "o solicitante",
            "a solicitante",
            "solicitante informou",
            "solicitante reportou",
            "solicitante relatou",
            "o colaborador",
            "a colaboradora",
            "informou inicialmente",
            "depois acrescentou",
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
    def _first_person_fallback_text(text: str) -> str:
        normalized = " ".join((text or "").strip().split())
        if not normalized:
            return ""
        replacements = (
            (r"^O usuario informou inicialmente:\s*", ""),
            (r"^O usuário informou inicialmente:\s*", ""),
            (r"\bDepois, acrescentou estes detalhes:\s*", ". "),
            (r"\b\d+\.\s+", ""),
        )
        for pattern, replacement in replacements:
            normalized = re.sub(pattern, replacement, normalized, flags=re.IGNORECASE)
        normalized = re.sub(r"\s+", " ", normalized).strip(" .")
        if not normalized:
            return ""
        if normalized.endswith(("!", "?")):
            return normalized
        return normalized + "."

    @staticmethod
    def _normalize_text(text: str) -> str:
        normalized = unicodedata.normalize("NFKD", text.casefold())
        normalized = "".join(
            char for char in normalized if not unicodedata.combining(char)
        )
        return re.sub(r"\s+", " ", normalized).strip()

    @classmethod
    def _normalize_status(cls, raw_status: Any) -> str:
        normalized = cls._normalize_text(str(raw_status))
        if normalized in {"organized", "organizado", "organizada"}:
            return "organized"
        if normalized in {
            "needs clarification",
            "needs_clarification",
            "need clarification",
            "clarification",
            "esclarecimento",
            "precisa esclarecimento",
            "precisa de esclarecimento",
        }:
            return "needs_clarification"
        return "needs_clarification"

    @classmethod
    def _normalize_confidence(cls, raw_confidence: Any) -> float:
        if isinstance(raw_confidence, int | float):
            return max(0.0, min(float(raw_confidence), 1.0))

        text = cls._normalize_text(str(raw_confidence))
        if not text:
            return 0.0

        match = re.search(r"\d+(?:[.,]\d+)?", text)
        if not match:
            return 0.0

        value = float(match.group(0).replace(",", "."))
        if "%" in str(raw_confidence) or value > 1.0:
            value /= 100.0
        return max(0.0, min(value, 1.0))

    @staticmethod
    def _build_system_prompt() -> str:
        return (
            "Voce organiza descricoes curtas de chamados de TI em portugues do Brasil.\n"
            "Responda somente JSON com: status, organized_text, clarification_question, confidence.\n"
            "Escreva sempre como relato do solicitante em primeira pessoa.\n"
            "Use organized quando o texto estiver claro e preserve a intencao original em uma frase curta.\n"
            "Preserve telas, codigos, numeros, mensagens de erro e nomes exatamente como foram enviados.\n"
            "Use needs_clarification somente quando o texto estiver vago demais.\n"
            "Nao invente causa, solucao, sistema, equipamento, setor, usuario ou gravidade.\n"
            "Nunca use terceira pessoa: 'o usuario', 'solicitante', 'reportou', 'relatou' ou 'informou'.\n"
            "Nao escreva frases como 'nao foi identificado', 'realize' ou 'provavelmente'."
        )

    @staticmethod
    def _build_user_prompt(
        user_text: str,
        category_name: str | None,
        purpose: str,
    ) -> str:
        return (
            f"Texto original do usuario: {user_text}\n\n"
            "Organize somente o texto original em primeira pessoa. "
            "Se ja estiver claro, apenas corrija pontuacao e pequenos erros.\n"
            "Se faltar contexto essencial, faca uma pergunta curta.\n\n"
            "Exemplo de estilo correto: Estou com problema de nota. Durante a visualizacao na tela 1234, "
            "a nota exibe o erro 123.456.789.\n"
            "Exemplo proibido: O usuario informou que esta com problema de nota.\n\n"
            "Retorne JSON neste formato:\n"
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
    client, backend_name = build_local_generative_client(settings)

    return GenerativeDescriptionOrganizer(
        client=client,
        backend_name=backend_name,
        max_input_chars=settings.ai_max_input_chars,
        max_output_chars=settings.ai_max_output_chars,
        num_predict=settings.ai_ollama_num_predict,
        num_thread=settings.ai_ollama_num_thread,
        temperature=settings.ai_ollama_temperature,
    )
