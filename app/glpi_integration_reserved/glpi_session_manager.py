class GLPISessionManager:
    """Mock session manager reserved for future GLPI token lifecycle."""

    def __init__(self) -> None:
        self._token: str | None = None

    def get_or_create_session_token(self) -> str:
        if self._token is None:
            self._token = "mock-glpi-session-token"
        return self._token

    def clear_session(self) -> None:
        self._token = None

