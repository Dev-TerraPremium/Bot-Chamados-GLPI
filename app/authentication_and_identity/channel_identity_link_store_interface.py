import abc
from app.authentication_and_identity.channel_identity_link_model import ChannelIdentityLink

class ChannelIdentityLinkStoreInterface(abc.ABC):
    @abc.abstractmethod
    def save(self, link: ChannelIdentityLink) -> None:
        pass

    @abc.abstractmethod
    def get(self, channel: str, channel_identifier: str) -> ChannelIdentityLink | None:
        pass

    @abc.abstractmethod
    def delete(self, channel: str, channel_identifier: str) -> None:
        pass
