from fastapi import APIRouter

from app.application_config.settings import load_settings
from app.distributed_runtime.redis_connection import get_redis_client
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


@router.get("/health/runtime")
def runtime_healthcheck() -> dict:
    settings = load_settings()
    redis_status = "disabled"
    if settings.is_redis_state_enabled:
        try:
            get_redis_client(settings.redis_url).ping()
            redis_status = "ok"
        except Exception:
            redis_status = "unavailable"

    return {
        "status": "ok" if redis_status in {"disabled", "ok"} else "degraded",
        "environment": settings.app_env,
        "state_backend": settings.state_backend,
        "redis": redis_status,
        "celery_workers_enabled": settings.use_celery_workers,
        "glpi_integration_mode": settings.glpi_integration_mode,
        "ai_guided_detailing_enabled": settings.ai_guided_detailing_enabled,
        "ai_max_clarification_questions": settings.ai_max_clarification_questions,
        "debug_routes_exposed": settings.expose_debug_routes,
    }
