from app.authentication_and_identity.authenticated_user_model import AuthenticatedUser
from app.authentication_and_identity.channel_identity_link_store_interface import ChannelIdentityLinkStoreInterface
from app.authentication_and_identity.channel_identity_link_model import ChannelIdentityLinkStatus
from app.authentication_and_identity.channel_identifier_normalizer import ChannelIdentifierNormalizer

class AuthenticatedUserResolver:
    def __init__(self, store: ChannelIdentityLinkStoreInterface):
        self.store = store

    def resolve(self, channel: str, channel_identifier: str) -> AuthenticatedUser | None:
        normalized_id = ChannelIdentifierNormalizer.normalize_phone(channel_identifier)
        link = self.store.get(channel, normalized_id)
        if link and link.status == ChannelIdentityLinkStatus.ACTIVE:
            return AuthenticatedUser(
                full_name=link.display_name or "Usuário",
                login=link.glpi_login or "login",
                email=link.email or "",
                glpi_user_id=link.glpi_user_id or 0
            )
        return None
