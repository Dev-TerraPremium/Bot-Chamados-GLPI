from __future__ import annotations

import logging
from typing import Iterable

from app.glpi_integration_reserved.glpi_future_real_client import (
    GLPIClientError,
    GLPIRealClient,
)
from app.ticket_notifications.models import TicketActivitySnapshot

logger = logging.getLogger(__name__)


RELATED_ITEMTYPES = (
    "ITILFollowup",
    "ITILSolution",
    "TicketTask",
    "TicketValidation",
    "Document_Item",
    "Ticket_User",
    "Group_Ticket",
)


class GLPITicketEventReader:
    def __init__(
        self,
        glpi_client: GLPIRealClient,
        *,
        related_itemtypes: Iterable[str] = RELATED_ITEMTYPES,
    ) -> None:
        self.glpi_client = glpi_client
        self.related_itemtypes = tuple(related_itemtypes)

    def read_snapshot(self, ticket_id: int) -> TicketActivitySnapshot:
        ticket = self.glpi_client.get_item("Ticket", ticket_id)
        related_items: dict[str, list[dict]] = {}
        for itemtype in self.related_itemtypes:
            related_items[itemtype] = self._read_related(ticket_id, itemtype)
        return TicketActivitySnapshot(
            ticket_id=ticket_id,
            ticket=ticket,
            related_items=related_items,
        )

    def _read_related(self, ticket_id: int, itemtype: str) -> list[dict]:
        try:
            response = self.glpi_client.get_ticket_related_items(ticket_id, itemtype)
        except GLPIClientError:
            logger.warning(
                "ticket_notification_related_read_failed",
                extra={"ticket_id": ticket_id, "itemtype": itemtype},
            )
            return []
        return [item for item in response.get("items", []) if isinstance(item, dict)]
