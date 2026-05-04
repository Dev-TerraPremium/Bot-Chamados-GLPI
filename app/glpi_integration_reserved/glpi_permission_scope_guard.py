class GLPIPermissionScopeGuard:
    """Simple user-scope guard for simulated GLPI responses."""

    def ensure_ticket_belongs_to_user(self, ticket, glpi_user_id: int) -> bool:
        return bool(ticket and ticket.glpi_user_id == glpi_user_id)

    def filter_visible_tickets(self, tickets: list, glpi_user_id: int) -> list:
        return [
            ticket
            for ticket in tickets
            if self.ensure_ticket_belongs_to_user(ticket, glpi_user_id)
        ]

