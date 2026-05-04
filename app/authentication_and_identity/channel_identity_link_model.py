from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ChannelIdentityLink:
    channel: str
    channel_user_identifier: str
    internal_login: str
    glpi_user_id: int


@dataclass(frozen=True, slots=True)
class SimulatedSessionIdentity:
    session_id: str
    channel: str
    login: str
    glpi_user_id: int

