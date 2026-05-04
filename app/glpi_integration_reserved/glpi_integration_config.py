import os
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class GLPIIntegrationConfig:
    base_url: str = ""
    app_token: str = ""
    user_token: str = ""
    integration_mode: str = "mock"


def load_glpi_integration_config() -> GLPIIntegrationConfig:
    return GLPIIntegrationConfig(
        base_url=os.getenv("GLPI_BASE_URL", ""),
        app_token=os.getenv("GLPI_APP_TOKEN", ""),
        user_token=os.getenv("GLPI_USER_TOKEN", ""),
        integration_mode=os.getenv("GLPI_INTEGRATION_MODE", "mock"),
    )

