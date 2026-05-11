import base64

import httpx
import pytest

from app.glpi_integration_reserved.glpi_future_real_client import GLPIClientError
from app.glpi_integration_reserved.glpi_future_real_client import GLPIRealClient
from app.glpi_integration_reserved.glpi_integration_config import GLPIIntegrationConfig


class RecordingGLPIClient(GLPIRealClient):
    def __init__(self, config: GLPIIntegrationConfig) -> None:
        super().__init__(config)
        self.calls = []

    def _request(self, method: str, path: str, **kwargs):
        self.calls.append((method, path, kwargs))
        if path == "/initSession":
            return {"session_token": "session"}
        return True


def test_glpi_real_client_activates_profile_and_entity_after_session() -> None:
    client = RecordingGLPIClient(
        GLPIIntegrationConfig(
            base_url="https://glpi.local/apirest.php",
            app_token="app",
            user_token="user",
            default_profile_id=4,
            default_entity_id=3,
        )
    )

    assert client.init_session() == "session"

    assert client.calls[0][1] == "/initSession"
    assert client.calls[1][1] == "/changeActiveProfile"
    assert client.calls[1][2]["json"] == {"profiles_id": 4}
    assert client.calls[2][1] == "/changeActiveEntities"
    assert client.calls[2][2]["json"] == {"entities_id": 3, "is_recursive": True}


def test_glpi_real_client_requires_explicit_flag_for_http() -> None:
    client = GLPIRealClient(
        GLPIIntegrationConfig(
            base_url="http://glpi.local/apirest.php",
            app_token="app",
            user_token="user",
        )
    )

    with pytest.raises(GLPIClientError):
        client.init_session()


def test_glpi_real_client_uploads_attachment_after_ticket_creation() -> None:
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append((request.method, request.url.path))
        if request.url.path.endswith("/initSession"):
            return httpx.Response(200, json={"session_token": "session"})
        if request.url.path.endswith("/Ticket"):
            return httpx.Response(200, json={"id": 1234})
        if request.url.path.endswith("/Document"):
            return httpx.Response(200, json={"id": 55})
        if request.url.path.endswith("/Document_Item"):
            return httpx.Response(200, json={"id": 77})
        raise AssertionError(f"Unexpected request: {request.method} {request.url}")

    client = GLPIRealClient(
        GLPIIntegrationConfig(
            base_url="https://glpi.local/apirest.php",
            app_token="app",
            user_token="user",
        ),
        transport=httpx.MockTransport(handler),
    )
    ticket = client.create_ticket(
        {
            "title": "Wi-Fi",
            "severity": "Média",
            "description": "Wi-Fi caindo",
            "category_name": "WI-FI",
            "requester_login": "pedro.torres",
            "glpi_user_id": 266,
            "channel": "whatsapp",
            "location": "TI",
            "impact_label": "Afeta somente a mim",
            "evidence": "print",
            "opening_mode": "Abertura assistida",
            "glpi_input": {
                "name": "Wi-Fi",
                "content": "Wi-Fi caindo",
                "entities_id": 3,
                "itilcategories_id": 544,
                "_users_id_requester": 266,
                "type": 1,
                "urgency": 2,
                "impact": 2,
                "priority": 3,
                "status": 1,
            },
            "attachments": [
                {
                    "file_name": "erro.png",
                    "mime_type": "image/png",
                    "data_base64": base64.b64encode(b"fake").decode("ascii"),
                }
            ],
        }
    )

    assert ticket.ticket_number == 1234
    assert any(method == "POST" and path.endswith("/Document") for method, path in calls)
    assert any(method == "POST" and path.endswith("/Document_Item") for method, path in calls)


def test_glpi_real_client_retries_once_after_expired_session() -> None:
    calls: list[tuple[str, str, str | None]] = []
    session_counter = {"value": 1}

    def handler(request: httpx.Request) -> httpx.Response:
        session_token = request.headers.get("Session-Token")
        calls.append((request.method, request.url.path, session_token))
        if request.url.path.endswith("/initSession"):
            session_counter["value"] += 1
            return httpx.Response(200, json={"session_token": f"session-{session_counter['value']}"})
        if request.url.path.endswith("/listSearchOptions/ITILCategory"):
            if session_token == "session-1":
                return httpx.Response(401, json={"message": "unauthorized"})
            if session_token == "session-2":
                return httpx.Response(200, json={"ok": True})
        raise AssertionError(f"Unexpected request: {request.method} {request.url}")

    client = GLPIRealClient(
        GLPIIntegrationConfig(
            base_url="https://glpi.local/apirest.php",
            app_token="app",
            user_token="user",
        ),
        transport=httpx.MockTransport(handler),
    )
    client._session_token = "session-1"

    assert client.list_search_options("ITILCategory") == {"ok": True}
    assert [path for _, path, _ in calls].count("/apirest.php/initSession") == 1
    assert [
        token for _, path, token in calls if path == "/apirest.php/listSearchOptions/ITILCategory"
    ] == ["session-1", "session-2"]


def test_glpi_real_client_caps_session_retry_after_second_unauthorized() -> None:
    calls: list[tuple[str, str, str | None]] = []
    session_counter = {"value": 1}

    def handler(request: httpx.Request) -> httpx.Response:
        session_token = request.headers.get("Session-Token")
        calls.append((request.method, request.url.path, session_token))
        if request.url.path.endswith("/initSession"):
            session_counter["value"] += 1
            return httpx.Response(200, json={"session_token": f"session-{session_counter['value']}"})
        if request.url.path.endswith("/listSearchOptions/ITILCategory"):
            return httpx.Response(401, json={"message": "unauthorized"})
        raise AssertionError(f"Unexpected request: {request.method} {request.url}")

    client = GLPIRealClient(
        GLPIIntegrationConfig(
            base_url="https://glpi.local/apirest.php",
            app_token="app",
            user_token="user",
        ),
        transport=httpx.MockTransport(handler),
    )
    client._session_token = "session-1"

    with pytest.raises(GLPIClientError):
        client.list_search_options("ITILCategory")

    assert [path for _, path, _ in calls].count("/apirest.php/initSession") == 1
    assert [
        token for _, path, token in calls if path == "/apirest.php/listSearchOptions/ITILCategory"
    ] == ["session-1", "session-2"]
