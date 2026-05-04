from app.glpi_integration_reserved.glpi_client_interface import GLPIClientInterface


class GLPIFutureRealClient(GLPIClientInterface):
    """Prepared shape for the future GLPI REST API client.

    This class intentionally performs no network calls in the MVP.
    """

    def init_session(self) -> str:
        raise NotImplementedError("Real GLPI session is not implemented in this MVP.")

    def kill_session(self) -> None:
        raise NotImplementedError("Real GLPI session is not implemented in this MVP.")

    def create_ticket(self, ticket_data: dict):
        raise NotImplementedError("Real GLPI ticket creation is not implemented.")

    def get_my_tickets(self, user_id: int):
        raise NotImplementedError("Real GLPI ticket query is not implemented.")

    def get_ticket_by_id(self, ticket_id: int, user_id: int):
        raise NotImplementedError("Real GLPI ticket query is not implemented.")

    def add_followup(self, ticket_id: int, user_id: int, content: str):
        raise NotImplementedError("Real GLPI followup is not implemented.")

    def find_user_by_identifier(self, identifier: str):
        raise NotImplementedError("Real GLPI user lookup is not implemented.")

    def find_category_by_name(self, category_name: str):
        raise NotImplementedError("Real GLPI category lookup is not implemented.")

