import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")
load_dotenv(PROJECT_ROOT / ".env.local", override=True)

DEFAULT_TICKET_NOTIFICATION_DISABLED_EVENT_TYPES = (
    "ticket_urgency_changed,"
    "ticket_category_changed,"
    "ticket_taken_changed,"
    "ticket_group_responsible_linked,"
    "task_added,"
    "ticket_waiting_changed"
)


def _get_bool(name: str, default: bool = False) -> bool:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    return raw_value.strip().casefold() in {"1", "true", "yes", "sim", "on"}


def _get_int(name: str, default: int) -> int:
    raw_value = os.getenv(name)
    if raw_value is None or raw_value.strip() == "":
        return default
    return int(raw_value)


def _get_float(name: str, default: float) -> float:
    raw_value = os.getenv(name)
    if raw_value is None or raw_value.strip() == "":
        return default
    return float(raw_value)


@dataclass(frozen=True, slots=True)
class AppSettings:
    app_env: str = "local"
    app_name: str = "Assistente de Chamados TI"
    glpi_integration_mode: str = "mock"
    state_backend: str = "memory"
    use_celery_workers: bool = False
    local_light_ai_mode: str = "generative_ollama"
    local_ollama_enabled: bool = True
    ollama_base_url: str = "http://127.0.0.1:11434"
    local_generative_model: str = "qwen2.5:0.5b"
    local_generative_timeout_seconds: float = 30.0
    google_ai_api_key: str = ""
    google_ai_model: str = "gemini-3.1-flash-lite"
    google_ai_base_url: str = "https://generativelanguage.googleapis.com/v1beta"
    google_ai_timeout_seconds: float = 12.0
    google_ai_max_retries: int = 1
    google_ai_rpm_limit: int = 12
    google_ai_rpd_limit: int = 450
    google_ai_rate_limit_enabled: bool = True
    ai_guided_detailing_enabled: bool = True
    ai_max_clarification_questions: int = 5
    ai_generative_title_enabled: bool = False
    ai_max_input_chars: int = 1000
    ai_max_output_chars: int = 800
    ai_ollama_num_predict: int = 300
    ai_ollama_num_thread: int = 4
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
    glpi_allow_insecure_http: bool = False
    glpi_http_timeout_seconds: float = 20.0
    glpi_session_ttl_seconds: int = 600
    glpi_create_ticket_idempotency_ttl_seconds: int = 300
    glpi_ticket_requester_search_field: int = 4
    glpi_ticket_public_url_template: str = ""
    expose_debug_routes: bool = True
    channel_linking_mode: str = "mock"
    channel_link_cpf_prefix_length: int = 6
    channel_link_hmac_pepper: str = "changeme"
    channel_link_max_failed_attempts: int = 3
    channel_link_allow_web_simulator_auto_user: bool = True
    channel_link_active_ttl_seconds: int = 0
    channel_link_pending_ttl_seconds: int = 900
    channel_link_audit_ttl_seconds: int = 31536000
    ticket_notifications_enabled: bool = False
    ticket_notification_poll_interval_seconds: int = 30
    ticket_notification_batch_size: int = 50
    ticket_notification_retry_delay_seconds: int = 120
    ticket_notification_terminal_statuses: str = "5,6"
    ticket_notification_backfill_enabled: bool = True
    ticket_notification_backfill_interval_seconds: int = 900
    ticket_notification_backfill_user_limit: int = 20
    ticket_notification_backfill_tickets_per_user: int = 5
    ticket_notification_internal_numbers: str = ""
    ticket_notification_internal_update_numbers: str = ""
    ticket_notification_error_alert_numbers: str = ""
    ticket_notification_error_alert_cooldown_seconds: int = 300
    ticket_notification_error_alert_consecutive_failures: int = 3
    ticket_notification_include_private_events: bool = True
    ticket_notification_disabled_event_types: str = DEFAULT_TICKET_NOTIFICATION_DISABLED_EVENT_TYPES
    ticket_notification_watch_ttl_days: int = 30
    ticket_notification_dispatch_timeout_seconds: float = 5.0
    whatsapp_outbound_base_url: str = "http://whatsapp:8081"
    whatsapp_internal_api_token: str = ""
    teams_enabled: bool = False
    teams_app_id: str = ""
    teams_app_password: str = ""
    teams_tenant_id: str = ""
    teams_public_bot_endpoint: str = ""
    teams_auth_validation_enabled: bool = True
    teams_connector_timeout_seconds: float = 8.0

    @property
    def is_glpi_real_mode(self) -> bool:
        return self.glpi_integration_mode.casefold() == "real"

    @property
    def is_redis_state_enabled(self) -> bool:
        return self.state_backend.casefold() == "redis"

    @property
    def is_google_ai_mode(self) -> bool:
        return self.local_light_ai_mode.casefold() == "generative_google"

    @property
    def is_ollama_mode(self) -> bool:
        return self.local_light_ai_mode.casefold() in {"generative_ollama", "ollama"}

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
        if self.ticket_notifications_enabled:
            if not self.is_redis_state_enabled:
                raise RuntimeError("STATE_BACKEND=redis e obrigatorio para notificacoes.")
            if not self.whatsapp_internal_api_token:
                raise RuntimeError("WHATSAPP_INTERNAL_API_TOKEN e obrigatorio para notificacoes.")
        if self.teams_enabled:
            if not self.is_redis_state_enabled:
                raise RuntimeError("STATE_BACKEND=redis e obrigatorio para Microsoft Teams.")
            missing = []
            if not self.teams_app_id:
                missing.append("TEAMS_APP_ID")
            if not self.teams_app_password:
                missing.append("TEAMS_APP_PASSWORD")
            if not self.teams_public_bot_endpoint:
                missing.append("TEAMS_PUBLIC_BOT_ENDPOINT")
            if missing:
                raise RuntimeError(
                    "Configuracao Microsoft Teams incompleta: " + ", ".join(missing)
                )


def load_settings() -> AppSettings:
    settings = AppSettings(
        app_env=os.getenv("APP_ENV", "local"),
        app_name=os.getenv("APP_NAME", "Assistente de Chamados TI"),
        glpi_integration_mode=os.getenv("GLPI_INTEGRATION_MODE", "mock"),
        state_backend=os.getenv("STATE_BACKEND", "memory"),
        use_celery_workers=_get_bool("USE_CELERY_WORKERS", False),
        local_light_ai_mode=os.getenv("LOCAL_LIGHT_AI_MODE", "generative_ollama"),
        local_ollama_enabled=_get_bool("LOCAL_OLLAMA_ENABLED", True),
        ollama_base_url=os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434"),
        local_generative_model=os.getenv(
            "LOCAL_GENERATIVE_MODEL",
            "qwen2.5:0.5b",
        ),
        local_generative_timeout_seconds=_get_float(
            "LOCAL_GENERATIVE_TIMEOUT_SECONDS", 30.0
        ),
        google_ai_api_key=os.getenv("GOOGLE_AI_API_KEY", ""),
        google_ai_model=os.getenv("GOOGLE_AI_MODEL", "gemini-3.1-flash-lite"),
        google_ai_base_url=os.getenv(
            "GOOGLE_AI_BASE_URL",
            "https://generativelanguage.googleapis.com/v1beta",
        ),
        google_ai_timeout_seconds=_get_float("GOOGLE_AI_TIMEOUT_SECONDS", 12.0),
        google_ai_max_retries=_get_int("GOOGLE_AI_MAX_RETRIES", 1),
        google_ai_rpm_limit=_get_int("GOOGLE_AI_RPM_LIMIT", 12),
        google_ai_rpd_limit=_get_int("GOOGLE_AI_RPD_LIMIT", 450),
        google_ai_rate_limit_enabled=_get_bool("GOOGLE_AI_RATE_LIMIT_ENABLED", True),
        ai_guided_detailing_enabled=_get_bool("AI_GUIDED_DETAILING_ENABLED", True),
        ai_max_clarification_questions=_get_int("AI_MAX_CLARIFICATION_QUESTIONS", 5),
        ai_generative_title_enabled=_get_bool("AI_GENERATIVE_TITLE_ENABLED", False),
        ai_max_input_chars=_get_int("AI_MAX_INPUT_CHARS", 1000),
        ai_max_output_chars=_get_int("AI_MAX_OUTPUT_CHARS", 800),
        ai_ollama_num_predict=_get_int("AI_OLLAMA_NUM_PREDICT", 300),
        ai_ollama_num_thread=_get_int("AI_OLLAMA_NUM_THREAD", 4),
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
        glpi_allow_insecure_http=_get_bool("GLPI_ALLOW_INSECURE_HTTP", False),
        glpi_http_timeout_seconds=_get_float("GLPI_HTTP_TIMEOUT_SECONDS", 20.0),
        glpi_session_ttl_seconds=_get_int("GLPI_SESSION_TTL_SECONDS", 600),
        glpi_create_ticket_idempotency_ttl_seconds=_get_int(
            "GLPI_CREATE_TICKET_IDEMPOTENCY_TTL_SECONDS", 300
        ),
        glpi_ticket_requester_search_field=_get_int(
            "GLPI_TICKET_REQUESTER_SEARCH_FIELD", 4
        ),
        glpi_ticket_public_url_template=os.getenv("GLPI_TICKET_PUBLIC_URL_TEMPLATE", ""),
        expose_debug_routes=_get_bool("EXPOSE_DEBUG_ROUTES", True),
        channel_linking_mode=os.getenv("CHANNEL_LINKING_MODE", "mock"),
        channel_link_cpf_prefix_length=_get_int("CHANNEL_LINK_CPF_PREFIX_LENGTH", 6),
        channel_link_hmac_pepper=os.getenv("CHANNEL_LINK_HMAC_PEPPER", "changeme"),
        channel_link_max_failed_attempts=_get_int("CHANNEL_LINK_MAX_FAILED_ATTEMPTS", 3),
        channel_link_allow_web_simulator_auto_user=_get_bool("CHANNEL_LINK_ALLOW_WEB_SIMULATOR_AUTO_USER", True),
        channel_link_active_ttl_seconds=_get_int("CHANNEL_LINK_ACTIVE_TTL_SECONDS", 0),
        channel_link_pending_ttl_seconds=_get_int("CHANNEL_LINK_PENDING_TTL_SECONDS", 900),
        channel_link_audit_ttl_seconds=_get_int("CHANNEL_LINK_AUDIT_TTL_SECONDS", 31536000),
        ticket_notifications_enabled=_get_bool("TICKET_NOTIFICATIONS_ENABLED", False),
        ticket_notification_poll_interval_seconds=_get_int("TICKET_NOTIFICATION_POLL_INTERVAL_SECONDS", 30),
        ticket_notification_batch_size=_get_int("TICKET_NOTIFICATION_BATCH_SIZE", 50),
        ticket_notification_retry_delay_seconds=_get_int("TICKET_NOTIFICATION_RETRY_DELAY_SECONDS", 120),
        ticket_notification_terminal_statuses=os.getenv("TICKET_NOTIFICATION_TERMINAL_STATUSES", "5,6"),
        ticket_notification_backfill_enabled=_get_bool("TICKET_NOTIFICATION_BACKFILL_ENABLED", True),
        ticket_notification_backfill_interval_seconds=_get_int("TICKET_NOTIFICATION_BACKFILL_INTERVAL_SECONDS", 900),
        ticket_notification_backfill_user_limit=_get_int("TICKET_NOTIFICATION_BACKFILL_USER_LIMIT", 20),
        ticket_notification_backfill_tickets_per_user=_get_int("TICKET_NOTIFICATION_BACKFILL_TICKETS_PER_USER", 5),
        ticket_notification_internal_numbers=os.getenv("TICKET_NOTIFICATION_INTERNAL_NUMBERS", ""),
        ticket_notification_internal_update_numbers=os.getenv("TICKET_NOTIFICATION_INTERNAL_UPDATE_NUMBERS", ""),
        ticket_notification_error_alert_numbers=os.getenv("TICKET_NOTIFICATION_ERROR_ALERT_NUMBERS", ""),
        ticket_notification_error_alert_cooldown_seconds=_get_int("TICKET_NOTIFICATION_ERROR_ALERT_COOLDOWN_SECONDS", 300),
        ticket_notification_error_alert_consecutive_failures=_get_int("TICKET_NOTIFICATION_ERROR_ALERT_CONSECUTIVE_FAILURES", 3),
        ticket_notification_include_private_events=_get_bool("TICKET_NOTIFICATION_INCLUDE_PRIVATE_EVENTS", True),
        ticket_notification_disabled_event_types=os.getenv(
            "TICKET_NOTIFICATION_DISABLED_EVENT_TYPES",
            DEFAULT_TICKET_NOTIFICATION_DISABLED_EVENT_TYPES,
        ),
        ticket_notification_watch_ttl_days=_get_int("TICKET_NOTIFICATION_WATCH_TTL_DAYS", 30),
        ticket_notification_dispatch_timeout_seconds=_get_float("TICKET_NOTIFICATION_DISPATCH_TIMEOUT_SECONDS", 5.0),
        whatsapp_outbound_base_url=os.getenv("WHATSAPP_OUTBOUND_BASE_URL", "http://whatsapp:8081"),
        whatsapp_internal_api_token=os.getenv("WHATSAPP_INTERNAL_API_TOKEN", ""),
        teams_enabled=_get_bool("TEAMS_ENABLED", False),
        teams_app_id=os.getenv("TEAMS_APP_ID", ""),
        teams_app_password=os.getenv("TEAMS_APP_PASSWORD", ""),
        teams_tenant_id=os.getenv("TEAMS_TENANT_ID", ""),
        teams_public_bot_endpoint=os.getenv("TEAMS_PUBLIC_BOT_ENDPOINT", ""),
        teams_auth_validation_enabled=_get_bool("TEAMS_AUTH_VALIDATION_ENABLED", True),
        teams_connector_timeout_seconds=_get_float("TEAMS_CONNECTOR_TIMEOUT_SECONDS", 8.0),
    )
    settings.validate_runtime_requirements()
    return settings
