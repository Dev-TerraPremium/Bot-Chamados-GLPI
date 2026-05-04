from uuid import uuid4

from fastapi.testclient import TestClient

from app.glpi_integration_reserved.glpi_mock_client import GLPIMockClient
from app.main import app
from app.security_and_abuse_protection.suspicious_input_detector import (
    SuspiciousInputDetector,
)
from app.security_and_abuse_protection.user_scope_guard import UserScopeGuard
from app.simulated_persistence.in_memory_ticket_store import InMemoryTicketStore


client = TestClient(app)


def base_payload(glpi_user_id: int, title: str) -> dict:
    return {
        "requester_name": "Pedro Torres",
        "requester_login": "pedro.torres",
        "requester_email": "pedro.torres@empresa.local",
        "glpi_user_id": glpi_user_id,
        "channel": "web_simulator",
        "opening_mode": "Chamado detalhado",
        "category_id": 6,
        "category_name": "Acesso / Senha",
        "title": title,
        "description": title,
        "impact_id": 2,
        "impact_label": "Afeta somente voce, mas ainda consegue trabalhar",
        "severity": "Media",
        "location": "TI - Matriz",
        "evidence": "Nao informado",
    }


def test_suspicious_sql_text_is_detected() -> None:
    detector = SuspiciousInputDetector()

    assert detector.is_suspicious("SELECT * FROM glpi_tickets")
    assert detector.is_suspicious("<script>alert(1)</script>")


def test_suspicious_input_is_blocked_by_conversation_endpoint() -> None:
    session_id = str(uuid4())
    client.post(
        "/api/conversation/message",
        json={"session_id": session_id, "message": "__start__"},
    )
    response = client.post(
        "/api/conversation/message",
        json={"session_id": session_id, "message": "SELECT * FROM tickets"},
    )

    assert response.status_code == 200
    assert "seguranca" in response.json()["bot_message"]


def test_query_returns_only_authenticated_user_tickets() -> None:
    store = InMemoryTicketStore()
    glpi_client = GLPIMockClient(store)
    own_ticket = glpi_client.create_ticket(base_payload(1001, "Chamado proprio"))
    other_ticket = glpi_client.create_ticket(base_payload(2002, "Chamado de outro"))

    visible = UserScopeGuard().filter_tickets_for_user(
        1001,
        [own_ticket, other_ticket],
    )

    assert [ticket.ticket_number for ticket in visible] == [own_ticket.ticket_number]


def test_followup_only_allows_authenticated_user_ticket() -> None:
    store = InMemoryTicketStore()
    glpi_client = GLPIMockClient(store)
    own_ticket = glpi_client.create_ticket(base_payload(1001, "Chamado proprio"))
    other_ticket = glpi_client.create_ticket(base_payload(2002, "Chamado de outro"))

    assert glpi_client.get_ticket_by_id(other_ticket.ticket_number, 1001) is None
    assert glpi_client.add_followup(other_ticket.ticket_number, 1001, "teste") is None
    assert glpi_client.add_followup(own_ticket.ticket_number, 1001, "teste") is not None

