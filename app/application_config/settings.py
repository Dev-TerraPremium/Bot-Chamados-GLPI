import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")
load_dotenv(PROJECT_ROOT / ".env.local", override=True)


def _get_bool(name: str, default: bool = False) -> bool:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    return raw_value.strip().casefold() in {"1", "true", "yes", "sim", "on"}


def _get_int(name: str, default: int) -> int:
    return int(os.getenv(name, str(default)))


def _get_float(name: str, default: float) -> float:
    return float(os.getenv(name, str(default)))


@dataclass(frozen=True, slots=True)
class AppSettings:
    app_env: str = "local"
    app_name: str = "Assistente de Chamados TI"
    glpi_integration_mode: str = "mock"
    state_backend: str = "memory"
    use_celery_workers: bool = False
    local_light_ai_mode: str = "generative_ollama"
    ollama_base_url: str = "http://127.0.0.1:11434"
    local_generative_model: str = "qwen2.5:1.5b"
    local_generative_timeout_seconds: float = 30.0
    ai_guided_detailing_enabled: bool = True
    ai_max_clarification_questions: int = 5
    ai_max_input_chars: int = 1000
    ai_max_output_chars: int = 800
    ai_ollama_num_predict: int = 300
    ai_ollama_temperature: float = 0.1
    max_message_length: int = 1000
    rate_limit_messages_per_minute: int = 20
    rate_limit_messages_per_hour: int = 200
    session_ttl_seconds: int = 3600
    session_lock_timeout_seconds: int = 180
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"
    celery_task_always_eager: bool = False
    ai_queue_name: str = "ai_local"
    glpi_queue_name: str = "glpi_io"
    ai_task_timeout_seconds: int = 25
    glpi_task_timeout_seconds: int = 20
    glpi_base_url: str = ""
    glpi_app_token: str = ""
    glpi_user_token: str = ""
    glpi_default_entity_id: int = 0
    glpi_default_profile_id: int = 0
    glpi_default_requester_user_id: int = 0
    glpi_http_timeout_seconds: float = 20.0
    glpi_session_ttl_seconds: int = 600
    glpi_create_ticket_idempotency_ttl_seconds: int = 300
    glpi_ticket_requester_search_field: int = 4
    expose_debug_routes: bool = True
    channel_linking_mode: str = "mock"
    channel_link_cpf_prefix_length: int = 4
    channel_link_hmac_pepper: str = "changeme"
    channel_link_max_failed_attempts: int = 3
    channel_link_allow_web_simulator_auto_user: bool = True
    channel_link_active_ttl_seconds: int = 0
    channel_link_pending_ttl_seconds: int = 900
    channel_link_audit_ttl_seconds: int = 31536000

    @property
    def is_glpi_real_mode(self) -> bool:
        return self.glpi_integration_mode.casefold() == "real"

    @property
    def is_redis_state_enabled(self) -> bool:
        return self.state_backend.casefold() == "redis"

    def validate_runtime_requirements(self) -> None:
        if self.is_glpi_real_mode:
            missing = []
            if not self.glpi_base_url:
                missing.append("GLPI_BASE_URL")
            if not self.glpi_app_token:
                missing.append("GLPI_APP_TOKEN")
            if not self.glpi_user_token:
                missing.append("GLPI_USER_TOKEN")
            if not self.glpi_default_entity_id:
                missing.append("GLPI_DEFAULT_ENTITY_ID")
            if missing:
                raise RuntimeError(
                    "Configuracao GLPI real incompleta: " + ", ".join(missing)
                )
        if self.app_env.casefold() == "production":
            if not self.is_redis_state_enabled:
                raise RuntimeError("STATE_BACKEND=redis e obrigatorio em producao.")
            if not self.use_celery_workers:
                raise RuntimeError("USE_CELERY_WORKERS=true e obrigatorio em producao.")


def load_settings() -> AppSettings:
    settings = AppSettings(
        app_env=os.getenv("APP_ENV", "local"),
        app_name=os.getenv("APP_NAME", "Assistente de Chamados TI"),
        glpi_integration_mode=os.getenv("GLPI_INTEGRATION_MODE", "mock"),
        state_backend=os.getenv("STATE_BACKEND", "memory"),
        use_celery_workers=_get_bool("USE_CELERY_WORKERS", False),
        local_light_ai_mode=os.getenv("LOCAL_LIGHT_AI_MODE", "generative_ollama"),
        ollama_base_url=os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434"),
        local_generative_model=os.getenv(
            "LOCAL_GENERATIVE_MODEL",
            "qwen2.5:1.5b",
        ),
        local_generative_timeout_seconds=_get_float(
            "LOCAL_GENERATIVE_TIMEOUT_SECONDS", 30.0
        ),
        ai_guided_detailing_enabled=_get_bool("AI_GUIDED_DETAILING_ENABLED", True),
        ai_max_clarification_questions=_get_int("AI_MAX_CLARIFICATION_QUESTIONS", 5),
        ai_max_input_chars=_get_int("AI_MAX_INPUT_CHARS", 1000),
        ai_max_output_chars=_get_int("AI_MAX_OUTPUT_CHARS", 800),
        ai_ollama_num_predict=_get_int("AI_OLLAMA_NUM_PREDICT", 300),
        ai_ollama_temperature=_get_float("AI_OLLAMA_TEMPERATURE", 0.1),
        max_message_length=_get_int("MAX_MESSAGE_LENGTH", 1000),
        rate_limit_messages_per_minute=_get_int(
            "RATE_LIMIT_MESSAGES_PER_MINUTE", 20
        ),
        rate_limit_messages_per_hour=_get_int("RATE_LIMIT_MESSAGES_PER_HOUR", 200),
        session_ttl_seconds=_get_int("SESSION_TTL_SECONDS", 3600),
        session_lock_timeout_seconds=_get_int("SESSION_LOCK_TIMEOUT_SECONDS", 180),
        redis_url=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
        celery_broker_url=os.getenv(
            "CELERY_BROKER_URL", "redis://localhost:6379/1"
        ),
        celery_result_backend=os.getenv(
            "CELERY_RESULT_BACKEND", "redis://localhost:6379/2"
        ),
        celery_task_always_eager=_get_bool("CELERY_TASK_ALWAYS_EAGER", False),
        ai_queue_name=os.getenv("AI_QUEUE_NAME", "ai_local"),
        glpi_queue_name=os.getenv("GLPI_QUEUE_NAME", "glpi_io"),
        ai_task_timeout_seconds=_get_int("AI_TASK_TIMEOUT_SECONDS", 25),
        glpi_task_timeout_seconds=_get_int("GLPI_TASK_TIMEOUT_SECONDS", 20),
        glpi_base_url=os.getenv("GLPI_BASE_URL", ""),
        glpi_app_token=os.getenv("GLPI_APP_TOKEN", ""),
        glpi_user_token=os.getenv("GLPI_USER_TOKEN", ""),
        glpi_default_entity_id=_get_int("GLPI_DEFAULT_ENTITY_ID", 0),
        glpi_default_profile_id=_get_int("GLPI_DEFAULT_PROFILE_ID", 0),
        glpi_default_requester_user_id=_get_int(
            "GLPI_DEFAULT_REQUESTER_USER_ID", 0
        ),
        glpi_http_timeout_seconds=_get_float("GLPI_HTTP_TIMEOUT_SECONDS", 20.0),
        glpi_session_ttl_seconds=_get_int("GLPI_SESSION_TTL_SECONDS", 600),
        glpi_create_ticket_idempotency_ttl_seconds=_get_int(
            "GLPI_CREATE_TICKET_IDEMPOTENCY_TTL_SECONDS", 300
        ),
        glpi_ticket_requester_search_field=_get_int(
            "GLPI_TICKET_REQUESTER_SEARCH_FIELD", 4
        ),
        expose_debug_routes=_get_bool("EXPOSE_DEBUG_ROUTES", True),
        channel_linking_mode=os.getenv("CHANNEL_LINKING_MODE", "mock"),
        channel_link_cpf_prefix_length=_get_int("CHANNEL_LINK_CPF_PREFIX_LENGTH", 4),
        channel_link_hmac_pepper=os.getenv("CHANNEL_LINK_HMAC_PEPPER", "changeme"),
        channel_link_max_failed_attempts=_get_int("CHANNEL_LINK_MAX_FAILED_ATTEMPTS", 3),
        channel_link_allow_web_simulator_auto_user=_get_bool("CHANNEL_LINK_ALLOW_WEB_SIMULATOR_AUTO_USER", True),
        channel_link_active_ttl_seconds=_get_int("CHANNEL_LINK_ACTIVE_TTL_SECONDS", 0),
        channel_link_pending_ttl_seconds=_get_int("CHANNEL_LINK_PENDING_TTL_SECONDS", 900),
        channel_link_audit_ttl_seconds=_get_int("CHANNEL_LINK_AUDIT_TTL_SECONDS", 31536000),
    )
    settings.validate_runtime_requirements()
    return settings
