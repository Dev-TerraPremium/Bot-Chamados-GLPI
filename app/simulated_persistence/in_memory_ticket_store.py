from itertools import count

from app.shared_kernel.date_time_provider import DateTimeProvider
from app.ticket_domain.ticket_enums import TicketStatus
from app.ticket_domain.ticket_models import TicketCreated, TicketFollowup


class InMemoryTicketStore:
    def __init__(self) -> None:
        self._ticket_counter = count(10001)
        self._tickets_by_number: dict[int, TicketCreated] = {}

    def create_ticket(self, payload: dict) -> TicketCreated:
        ticket_number = next(self._ticket_counter)
        ticket = TicketCreated(
            ticket_number=ticket_number,
            title=payload["title"],
            status=TicketStatus.OPEN.value,
            severity=payload["severity"],
            description=payload["description"],
            category_name=payload["category_name"],
            requester_login=payload["requester_login"],
            glpi_user_id=payload["glpi_user_id"],
            channel=payload["channel"],
            location=payload["location"],
            impact_label=payload["impact_label"],
            evidence=payload.get("evidence") or "Não informado",
            opening_mode=payload["opening_mode"],
            created_at=DateTimeProvider.utc_now_iso(),
        )
        self._tickets_by_number[ticket_number] = ticket
        return ticket

    def list_by_user(self, glpi_user_id: int) -> list[TicketCreated]:
        tickets = [
            ticket
            for ticket in self._tickets_by_number.values()
            if ticket.glpi_user_id == glpi_user_id
        ]
        return sorted(tickets, key=lambda ticket: ticket.ticket_number, reverse=True)

    def get_by_number(self, ticket_number: int) -> TicketCreated | None:
        return self._tickets_by_number.get(ticket_number)

    def add_followup(
        self, ticket_number: int, glpi_user_id: int, content: str
    ) -> TicketFollowup | None:
        ticket = self.get_by_number(ticket_number)
        if ticket is None or ticket.glpi_user_id != glpi_user_id:
            return None

        followup = TicketFollowup(
            ticket_number=ticket_number,
            user_id=glpi_user_id,
            content=content,
            created_at=DateTimeProvider.utc_now_iso(),
        )
        ticket.followups.append(followup)
        return followup

    def clear(self) -> None:
        self._tickets_by_number.clear()
        self._ticket_counter = count(10001)
