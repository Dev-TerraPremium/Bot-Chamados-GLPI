from app.authentication_and_identity.authenticated_user_model import AuthenticatedUser
from app.shared_kernel.constants import (
    DEFAULT_GLPI_USER_ID,
    DEFAULT_USER_EMAIL,
    DEFAULT_USER_LOGIN,
    DEFAULT_USER_NAME,
)


class SimulatedAuthService:
    """Returns the same authenticated user for this local MVP."""

    def authenticate_session(self, session_id: str, channel: str) -> AuthenticatedUser:
        return AuthenticatedUser(
            full_name=DEFAULT_USER_NAME,
            login=DEFAULT_USER_LOGIN,
            email=DEFAULT_USER_EMAIL,
            glpi_user_id=DEFAULT_GLPI_USER_ID,
        )

