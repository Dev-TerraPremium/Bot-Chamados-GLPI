import fakeredis
import pytest
from fastapi.testclient import TestClient

from app.application_config.settings import AppSettings
from app.channel_adapters.microsoft_teams_adapter import MicrosoftTeamsAdapter
from app.main import app
from app.microsoft_teams.adaptive_cards import TeamsAdaptiveCardRenderer
from app.microsoft_teams.bot_framework_client import TeamsSendResult
from app.microsoft_teams.conversation_reference_store import TeamsConversationReferenceStore
from app.shared_kernel.result_types import ConversationTurnResult


class FakeFlowController:
    def __init__(self):
        self.calls = []

    def process_message(self, **kwargs):
        self.calls.append(kwargs)
        return ConversationTurnResult(
            session_id=kwargs["session_id"],
            bot_message="Resposta do bot",
            state="main_menu",
        )


class FakeTeamsClient:
    def __init__(self):
        self.sent = []

    def send_activity(self, reference, **kwargs):
        self.sent.append((reference, kwargs))
        return TeamsSendResult(ok=True)


def teams_activity(text: str = "<at>Bot</at> Abrir chamado") -> dict:
    return {
        "type": "message",
        "id": "activity-id",
        "channelId": "msteams",
        "serviceUrl": "https://smba.trafficmanager.net/teams/",
        "from": {
            "id": "29:user-id",
            "aadObjectId": "aad-user-id",
            "name": "Pedro Torres",
        },
        "recipient": {"id": "28:bot-id", "name": "Bot"},
        "conversation": {"id": "conversation-id", "conversationType": "personal"},
        "channelData": {"tenant": {"id": "tenant-id"}},
        "text": text,
    }


def test_teams_adapter_saves_reference_and_sends_engine_response():
    redis_client = fakeredis.FakeRedis(decode_responses=True)
    store = TeamsConversationReferenceStore(redis_client)
    client = FakeTeamsClient()
    flow = FakeFlowController()
    adapter = MicrosoftTeamsAdapter(
        flow_controller=flow,
        reference_store=store,
        client=client,
        card_renderer=TeamsAdaptiveCardRenderer(
            "https://glpi.local/front/ticket.form.php?id={ticket_id}"
        ),
    )

    result = adapter.receive_activity(teams_activity())

    assert result["status"] == "ok"
    assert flow.calls[0]["channel"] == "teams"
    assert flow.calls[0]["channel_identifier"] == "aad-user-id"
    assert flow.calls[0]["message"] == "Abrir chamado"
    assert store.get("aad-user-id").conversation_id == "conversation-id"
    assert client.sent[0][1]["text"] == "Resposta do bot"
    assert client.sent[0][1]["reply_to_activity_id"] == "activity-id"


def test_teams_adapter_uses_card_for_created_ticket():
    redis_client = fakeredis.FakeRedis(decode_responses=True)
    store = TeamsConversationReferenceStore(redis_client)
    client = FakeTeamsClient()

    class CreatedTicketFlow(FakeFlowController):
        def process_message(self, **kwargs):
            return ConversationTurnResult(
                session_id=kwargs["session_id"],
                bot_message="Chamado aberto",
                state="main_menu",
                bot_messages=["Chamado aberto", "Menu"],
                created_ticket={
                    "ticket_number": 9274,
                    "category_name": "Sistemas",
                    "severity": "Média",
                },
            )

    adapter = MicrosoftTeamsAdapter(
        flow_controller=CreatedTicketFlow(),
        reference_store=store,
        client=client,
        card_renderer=TeamsAdaptiveCardRenderer(
            "https://glpi.local/front/ticket.form.php?id={ticket_id}"
        ),
    )

    adapter.receive_activity(teams_activity("Confirmar"))

    first_payload = client.sent[0][1]
    assert first_payload["attachments"][0]["content"]["actions"][0]["url"].endswith("id=9274")
    assert client.sent[1][1]["text"] == "Menu"


def test_teams_route_returns_404_when_disabled(monkeypatch):
    monkeypatch.setattr(
        "app.api_http_routes.teams_routes.load_settings",
        lambda: AppSettings(teams_enabled=False),
    )
    response = TestClient(app).post("/api/teams/messages", json=teams_activity())
    assert response.status_code == 404
