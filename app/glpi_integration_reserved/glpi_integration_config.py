import os
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class GLPIIntegrationConfig:
    base_url: str = ""
    app_token: str = ""
    user_token: str = ""
    integration_mode: str = "mock"
    default_entity_id: int = 0
    default_profile_id: int = 0
    default_requester_user_id: int = 0
    http_timeout_seconds: float = 20.0
    ticket_requester_search_field: int = 4

    @property
    def normalized_base_url(self) -> str:
        return self.base_url.rstrip("/")


def load_glpi_integration_config() -> GLPIIntegrationConfig:
    return GLPIIntegrationConfig(
        base_url=os.getenv("GLPI_BASE_URL", ""),
        app_token=os.getenv("GLPI_APP_TOKEN", ""),
        user_token=os.getenv("GLPI_USER_TOKEN", ""),
        integration_mode=os.getenv("GLPI_INTEGRATION_MODE", "mock"),
        default_entity_id=int(os.getenv("GLPI_DEFAULT_ENTITY_ID", "0")),
        default_profile_id=int(os.getenv("GLPI_DEFAULT_PROFILE_ID", "0")),
        default_requester_user_id=int(
            os.getenv("GLPI_DEFAULT_REQUESTER_USER_ID", "0")
        ),
        http_timeout_seconds=float(os.getenv("GLPI_HTTP_TIMEOUT_SECONDS", "20")),
        ticket_requester_search_field=int(
            os.getenv("GLPI_TICKET_REQUESTER_SEARCH_FIELD", "4")
        ),
    )
