from app.authentication_and_identity.authenticated_user_model import AuthenticatedUser
from app.shared_kernel.constants import (
    DEFAULT_GLPI_USER_ID,
    DEFAULT_USER_EMAIL,
    DEFAULT_USER_LOGIN,
    DEFAULT_USER_NAME,
)


class InMemoryUserStore:
    def __init__(self) -> None:
        self._users_by_login = {
            DEFAULT_USER_LOGIN: AuthenticatedUser(
                full_name=DEFAULT_USER_NAME,
                login=DEFAULT_USER_LOGIN,
                email=DEFAULT_USER_EMAIL,
                glpi_user_id=DEFAULT_GLPI_USER_ID,
            )
        }

    def get_by_login(self, login: str) -> AuthenticatedUser | None:
        return self._users_by_login.get(login)

    def get_default_user(self) -> AuthenticatedUser:
        return self._users_by_login[DEFAULT_USER_LOGIN]

