from app.glpi_integration_reserved.glpi_client_interface import GLPIClientInterface
from app.simulated_persistence.in_memory_ticket_store import InMemoryTicketStore
from app.triage_rules.category_catalog import get_category_by_name


class GLPIMockClient(GLPIClientInterface):
    """Mock GLPI client backed by the in-memory ticket store."""

    def __init__(self, ticket_store: InMemoryTicketStore) -> None:
        self.ticket_store = ticket_store
        self._session_token: str | None = None

    def init_session(self) -> str:
        self._session_token = "mock-glpi-session-token"
        return self._session_token

    def kill_session(self) -> None:
        self._session_token = None

    def create_ticket(self, ticket_data: dict):
        if self._session_token is None:
            self.init_session()
        return self.ticket_store.create_ticket(ticket_data)

    def get_my_tickets(self, user_id: int):
        return self.ticket_store.list_by_user(user_id)

    def get_ticket_by_id(self, ticket_id: int, user_id: int):
        ticket = self.ticket_store.get_by_number(ticket_id)
        if ticket is None or ticket.glpi_user_id != user_id:
            return None
        return ticket

    def add_followup(self, ticket_id: int, user_id: int, content: str):
        return self.ticket_store.add_followup(ticket_id, user_id, content)

    def find_user_by_identifier(self, identifier: str):
        return {
            "identifier": identifier,
            "glpi_user_id": 1001,
            "mode": "mock",
        }

    def find_category_by_name(self, category_name: str):
        category = get_category_by_name(category_name)
        if category is None:
            return None
        return {
            "internal_category_id": category.id,
            "internal_category_name": category.name,
            "future_glpi_category_id": category.id,
        }

