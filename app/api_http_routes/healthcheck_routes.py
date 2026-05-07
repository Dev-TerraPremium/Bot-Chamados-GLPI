from fastapi import APIRouter

from app.application_config.settings import load_settings
from app.distributed_runtime.redis_connection import get_redis_client
from app.glpi_integration_reserved.glpi_future_real_client import (
    GLPIClientError,
    GLPIRealClient,
)
from app.glpi_integration_reserved.glpi_integration_config import GLPIIntegrationConfig
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


@router.get("/health/glpi")
def glpi_healthcheck() -> dict:
    settings = load_settings()
    if not settings.is_glpi_real_mode:
        return {
            "status": "disabled",
            "glpi_integration_mode": settings.glpi_integration_mode,
        }

    client = GLPIRealClient(
        GLPIIntegrationConfig(
            base_url=settings.glpi_base_url,
            app_token=settings.glpi_app_token,
            user_token=settings.glpi_user_token,
            integration_mode=settings.glpi_integration_mode,
            default_entity_id=settings.glpi_default_entity_id,
            default_profile_id=settings.glpi_default_profile_id,
            default_requester_user_id=settings.glpi_default_requester_user_id,
            allow_insecure_http=settings.glpi_allow_insecure_http,
            http_timeout_seconds=settings.glpi_http_timeout_seconds,
            ticket_requester_search_field=settings.glpi_ticket_requester_search_field,
        )
    )
    try:
        return client.healthcheck()
    except GLPIClientError as exc:
        return {
            "status": "degraded",
            "error": str(exc),
        }
