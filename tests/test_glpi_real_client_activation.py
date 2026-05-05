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
