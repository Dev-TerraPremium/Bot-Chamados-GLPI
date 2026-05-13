from __future__ import annotations

import hashlib
import re

from app.conversation_engine.conversation_flow_controller import ConversationFlowController
from app.microsoft_teams.adaptive_cards import TeamsAdaptiveCardRenderer
from app.microsoft_teams.bot_framework_client import TeamsBotFrameworkClient
from app.microsoft_teams.conversation_reference_store import TeamsConversationReferenceStore
from app.shared_kernel.result_types import ConversationTurnResult


class MicrosoftTeamsAdapter:
    """Translates Microsoft Teams activities into conversation engine calls."""

    def __init__(
        self,
        *,
        flow_controller: ConversationFlowController,
        reference_store: TeamsConversationReferenceStore,
        client: TeamsBotFrameworkClient,
        card_renderer: TeamsAdaptiveCardRenderer,
    ) -> None:
        self.flow_controller = flow_controller
        self.reference_store = reference_store
        self.client = client
        self.card_renderer = card_renderer

    def receive_activity(self, activity: dict) -> dict:
        channel_identifier = self._channel_identifier(activity)
        if channel_identifier:
            self.reference_store.save_from_activity(channel_identifier, activity)

        activity_type = str(activity.get("type") or "").casefold()
        if activity_type == "conversationupdate":
            return {"status": "ok", "activity": "conversationUpdate"}
        if activity_type != "message":
            return {"status": "ignored", "activity": activity_type}

        text = self._clean_message_text(str(activity.get("text") or ""))
        result = self.flow_controller.process_message(
            session_id=self._session_id(channel_identifier),
            message=text,
            channel="teams",
            channel_identifier=channel_identifier,
        )
        self._send_result(activity, channel_identifier, result)
        return {"status": "ok", "state": result.state}

    def _send_result(
        self,
        activity: dict,
        channel_identifier: str,
        result: ConversationTurnResult,
    ) -> None:
        reference = self.reference_store.get(channel_identifier)
        if reference is None:
            return

        reply_to_activity_id = str(activity.get("id") or "")
        messages = result.bot_messages or [result.bot_message]
        if result.created_ticket:
            card = self.card_renderer.attachment(
                self.card_renderer.ticket_opened_card(result.created_ticket)
            )
            self.client.send_activity(
                reference,
                text=result.bot_message,
                attachments=[card],
                reply_to_activity_id=reply_to_activity_id,
            )
            for message in messages[1:]:
                self.client.send_activity(
                    reference,
                    text=message,
                    reply_to_activity_id=reply_to_activity_id,
                )
            return

        for message in messages:
            self.client.send_activity(
                reference,
                text=message,
                reply_to_activity_id=reply_to_activity_id,
            )

    @staticmethod
    def _channel_identifier(activity: dict) -> str:
        sender = activity.get("from") or {}
        return str(sender.get("aadObjectId") or sender.get("id") or "").strip()

    @staticmethod
    def _session_id(channel_identifier: str) -> str:
        digest = hashlib.sha256(channel_identifier.encode("utf-8")).hexdigest()[:32]
        return f"teams:{digest}"

    @staticmethod
    def _clean_message_text(text: str) -> str:
        text = re.sub(r"<at>.*?</at>", "", text, flags=re.IGNORECASE)
        text = re.sub(r"<[^>]+>", "", text)
        return text.strip()
