import os
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AppSettings:
    app_env: str = "local"
    app_name: str = "Assistente de Chamados TI"
    glpi_integration_mode: str = "mock"
    local_light_ai_mode: str = "generative_ollama"
    ollama_base_url: str = "http://127.0.0.1:11434"
    local_generative_model: str = "hf.co/Qwen/Qwen3-0.6B-GGUF:Q8_0"
    local_generative_timeout_seconds: float = 30.0
    max_message_length: int = 1000
    rate_limit_messages_per_minute: int = 20


def load_settings() -> AppSettings:
    return AppSettings(
        app_env=os.getenv("APP_ENV", "local"),
        app_name=os.getenv("APP_NAME", "Assistente de Chamados TI"),
        glpi_integration_mode=os.getenv("GLPI_INTEGRATION_MODE", "mock"),
        local_light_ai_mode=os.getenv("LOCAL_LIGHT_AI_MODE", "generative_ollama"),
        ollama_base_url=os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434"),
        local_generative_model=os.getenv(
            "LOCAL_GENERATIVE_MODEL",
            "hf.co/Qwen/Qwen3-0.6B-GGUF:Q8_0",
        ),
        local_generative_timeout_seconds=float(
            os.getenv("LOCAL_GENERATIVE_TIMEOUT_SECONDS", "30")
        ),
        max_message_length=int(os.getenv("MAX_MESSAGE_LENGTH", "1000")),
        rate_limit_messages_per_minute=int(
            os.getenv("RATE_LIMIT_MESSAGES_PER_MINUTE", "20")
        ),
    )
