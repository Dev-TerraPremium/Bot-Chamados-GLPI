class GLPIUserLookupService:
    """Mocked lookup facade for future AD, GLPI and channel identity mapping."""

    def find_glpi_user_for_authenticated_user(self, authenticated_user) -> dict:
        return {
            "glpi_user_id": authenticated_user.glpi_user_id,
            "login": authenticated_user.login,
            "email": authenticated_user.email,
            "source": "mock_authenticated_user",
        }

    def find_by_channel_identifier(self, channel: str, identifier: str) -> dict | None:
        return {
            "channel": channel,
            "identifier": identifier,
            "glpi_user_id": 1001,
            "source": "mock_channel_link",
        }

