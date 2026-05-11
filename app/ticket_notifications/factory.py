from __future__ import annotations

from app.application_config.settings import AppSettings, load_settings
from app.distributed_runtime.redis_connection import get_redis_client
from app.glpi_integration_reserved.glpi_future_real_client import GLPIRealClient
from app.glpi_integration_reserved.glpi_integration_config import GLPIIntegrationConfig
from app.ticket_notifications.event_reader import GLPITicketEventReader
from app.ticket_notifications.pipeline import TicketNotificationPipeline
from app.ticket_notifications.whatsapp_dispatcher import WhatsAppNotificationDispatcher


def build_notification_glpi_client(settings: AppSettings) -> GLPIRealClient:
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


def build_notification_pipeline(
    settings: AppSettings | None = None,
) -> TicketNotificationPipeline:
    settings = settings or load_settings()
    redis_client = get_redis_client(settings.redis_url)
    glpi_client = build_notification_glpi_client(settings)
    dispatcher = WhatsAppNotificationDispatcher(
        base_url=settings.whatsapp_outbound_base_url,
        internal_token=settings.whatsapp_internal_api_token,
    )
    return TicketNotificationPipeline(
        settings=settings,
        redis_client=redis_client,
        event_reader=GLPITicketEventReader(glpi_client),
        dispatcher=dispatcher,
    )
