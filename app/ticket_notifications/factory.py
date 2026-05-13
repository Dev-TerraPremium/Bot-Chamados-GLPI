from __future__ import annotations

from app.application_config.settings import AppSettings, load_settings
from app.distributed_runtime.redis_connection import get_redis_client
from app.glpi_integration_reserved.glpi_future_real_client import GLPIRealClient
from app.glpi_integration_reserved.glpi_integration_config import GLPIIntegrationConfig
from app.ticket_notifications.backfill import TicketNotificationBackfillService
from app.ticket_notifications.event_detector import TicketEventDetector
from app.ticket_notifications.event_reader import GLPITicketEventReader
from app.ticket_notifications.event_store import TicketNotificationStore
from app.ticket_notifications.metrics_recorder import NotificationMetricsRecorder
from app.ticket_notifications.pipeline import TicketNotificationPipeline
from app.ticket_notifications.whatsapp_dispatcher import WhatsAppNotificationDispatcher
from app.microsoft_teams.adaptive_cards import TeamsAdaptiveCardRenderer
from app.microsoft_teams.bot_framework_client import TeamsBotFrameworkClient
from app.microsoft_teams.conversation_reference_store import TeamsConversationReferenceStore
from app.microsoft_teams.dispatcher import TeamsNotificationDispatcher


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
    store = TicketNotificationStore(
        redis_client,
        watch_ttl_days=settings.ticket_notification_watch_ttl_days,
    )
    detector = TicketEventDetector(store)
    event_reader = GLPITicketEventReader(glpi_client)
    metrics = NotificationMetricsRecorder(redis_client)
    dispatcher = WhatsAppNotificationDispatcher(
        base_url=settings.whatsapp_outbound_base_url,
        internal_token=settings.whatsapp_internal_api_token,
        timeout_seconds=settings.ticket_notification_dispatch_timeout_seconds,
    )
    backfill_service = TicketNotificationBackfillService(
        settings=settings,
        redis_client=redis_client,
        glpi_client=glpi_client,
        store=store,
        event_reader=event_reader,
        detector=detector,
        metrics=metrics,
    )
    teams_dispatcher = None
    if settings.teams_enabled:
        teams_dispatcher = TeamsNotificationDispatcher(
            reference_store=TeamsConversationReferenceStore(
                redis_client,
                ttl_seconds=settings.channel_link_audit_ttl_seconds,
            ),
            client=TeamsBotFrameworkClient(settings),
            card_renderer=TeamsAdaptiveCardRenderer(
                settings.glpi_ticket_public_url_template
            ),
        )
    return TicketNotificationPipeline(
        settings=settings,
        redis_client=redis_client,
        event_reader=event_reader,
        dispatcher=dispatcher,
        store=store,
        detector=detector,
        metrics=metrics,
        backfill_service=backfill_service,
        teams_dispatcher=teams_dispatcher,
    )
