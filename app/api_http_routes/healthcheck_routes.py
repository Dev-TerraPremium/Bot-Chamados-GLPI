from fastapi import APIRouter

from app.application_config.settings import load_settings
from app.shared_kernel.common_response_models import HealthResponse


router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def healthcheck() -> HealthResponse:
    settings = load_settings()
    return HealthResponse(
        status="ok",
        app_name=settings.app_name,
        environment=settings.app_env,
        glpi_integration_mode=settings.glpi_integration_mode,
    )

