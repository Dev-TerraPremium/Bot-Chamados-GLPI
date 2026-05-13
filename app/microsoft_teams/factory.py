from __future__ import annotations

from app.application_config.settings import AppSettings
from app.channel_adapters.microsoft_teams_adapter import MicrosoftTeamsAdapter
from app.conversation_engine.conversation_flow_controller import ConversationFlowController
from app.distributed_runtime.redis_connection import get_redis_client
from app.microsoft_teams.adaptive_cards import TeamsAdaptiveCardRenderer
from app.microsoft_teams.bot_framework_client import TeamsBotFrameworkClient
from app.microsoft_teams.conversation_reference_store import TeamsConversationReferenceStore


def build_teams_adapter(
    settings: AppSettings,
    flow_controller: ConversationFlowController,
) -> MicrosoftTeamsAdapter:
    redis_client = get_redis_client(settings.redis_url)
    return MicrosoftTeamsAdapter(
        flow_controller=flow_controller,
        reference_store=TeamsConversationReferenceStore(
            redis_client,
            ttl_seconds=settings.channel_link_audit_ttl_seconds,
        ),
        client=TeamsBotFrameworkClient(settings),
        card_renderer=TeamsAdaptiveCardRenderer(settings.glpi_ticket_public_url_template),
    )
