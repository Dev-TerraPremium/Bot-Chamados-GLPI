from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AuthenticatedUser:
    full_name: str
    login: str
    email: str
    glpi_user_id: int

    @property
    def first_name(self) -> str:
        return self.full_name.split()[0]

    def to_safe_dict(self) -> dict:
        return {
            "full_name": self.full_name,
            "login": self.login,
            "email": self.email,
            "glpi_user_id": self.glpi_user_id,
        }

