from abc import ABC, abstractmethod


class GLPIClientInterface(ABC):
    @abstractmethod
    def init_session(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def kill_session(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def create_ticket(self, ticket_data: dict):
        raise NotImplementedError

    @abstractmethod
    def get_my_tickets(self, user_id: int):
        raise NotImplementedError

    @abstractmethod
    def get_ticket_by_id(self, ticket_id: int, user_id: int):
        raise NotImplementedError

    @abstractmethod
    def add_followup(self, ticket_id: int, user_id: int, content: str):
        raise NotImplementedError

    @abstractmethod
    def find_user_by_identifier(self, identifier: str):
        raise NotImplementedError

    @abstractmethod
    def find_category_by_name(self, category_name: str):
        raise NotImplementedError

