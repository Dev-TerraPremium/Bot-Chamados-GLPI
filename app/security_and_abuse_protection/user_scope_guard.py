from typing import Iterable


class UserScopeGuard:
    def can_access_ticket(self, authenticated_glpi_user_id: int, ticket) -> bool:
        return bool(ticket and ticket.glpi_user_id == authenticated_glpi_user_id)

    def filter_tickets_for_user(
        self, authenticated_glpi_user_id: int, tickets: Iterable
    ) -> list:
        return [
            ticket
            for ticket in tickets
            if self.can_access_ticket(authenticated_glpi_user_id, ticket)
        ]

