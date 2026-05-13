from __future__ import annotations

import logging
from dataclasses import dataclass

from app.microsoft_teams.adaptive_cards import TeamsAdaptiveCardRenderer
from app.microsoft_teams.bot_framework_client import TeamsBotFrameworkClient
from app.microsoft_teams.conversation_reference_store import TeamsConversationReferenceStore

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class TeamsDispatchResult:
    ok: bool
    detail: str = ""


class TeamsNotificationDispatcher:
    def __init__(
        self,
        *,
        reference_store: TeamsConversationReferenceStore,
        client: TeamsBotFrameworkClient,
        card_renderer: TeamsAdaptiveCardRenderer,
    ) -> None:
        self.reference_store = reference_store
        self.client = client
        self.card_renderer = card_renderer

    def send_ticket_update(
        self,
        channel_identifier: str,
        *,
        ticket_id: int,
        message: str,
    ) -> TeamsDispatchResult:
        reference = self.reference_store.get(channel_identifier)
        if reference is None:
            logger.info(
                "teams_conversation_reference_missing",
                extra={"channel_identifier": channel_identifier},
            )
            return TeamsDispatchResult(ok=False, detail="reference_missing")

        card = self.card_renderer.attachment(
            self.card_renderer.ticket_update_card(ticket_id, message)
        )
        result = self.client.send_activity(
            reference,
            text=message,
            attachments=[card],
        )
        return TeamsDispatchResult(ok=result.ok, detail=result.detail)
