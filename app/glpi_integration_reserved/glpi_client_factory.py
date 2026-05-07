from app.application_config.settings import AppSettings
from app.background_jobs.celery_glpi_client import CeleryGLPIClient
from app.glpi_integration_reserved.glpi_future_real_client import GLPIRealClient
from app.glpi_integration_reserved.glpi_integration_config import GLPIIntegrationConfig
from app.glpi_integration_reserved.glpi_mock_client import GLPIMockClient
from app.simulated_persistence.in_memory_ticket_store import InMemoryTicketStore


def build_glpi_client(settings: AppSettings, ticket_store: InMemoryTicketStore):
    if settings.use_celery_workers:
        return CeleryGLPIClient(settings)

    if not settings.is_glpi_real_mode:
        return GLPIMockClient(ticket_store)

    return GLPIRealClient(
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
