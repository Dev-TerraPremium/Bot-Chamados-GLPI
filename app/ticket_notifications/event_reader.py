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
        self._item_name_cache: dict[tuple[str, int], str] = {}

    def read_ticket(self, ticket_id: int) -> dict:
        return self.glpi_client.get_item("Ticket", ticket_id)

    def read_snapshot(
        self,
        ticket_id: int,
        *,
        ticket: dict | None = None,
    ) -> TicketActivitySnapshot:
        ticket = ticket or self.read_ticket(ticket_id)
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
        except GLPIClientError as exc:
            logger.warning(
                "ticket_notification_related_read_failed",
                extra={
                    "ticket_id": ticket_id,
                    "itemtype": itemtype,
                    "error": str(exc),
                },
            )
            raise
        items = [item for item in response.get("items", []) if isinstance(item, dict)]
        if itemtype == "Ticket_User":
            return [self._enrich_ticket_user(item) for item in items]
        if itemtype == "Group_Ticket":
            return [self._enrich_group_ticket(item) for item in items]
        return items

    def _enrich_ticket_user(self, item: dict) -> dict:
        user_id = self._int_value(item.get("users_id"))
        if not user_id:
            return item

        enriched = dict(item)
        enriched.setdefault("linked_type_label", self._ticket_actor_type_label(item.get("type")))
        name = self._get_item_display_name("User", user_id)
        if name:
            enriched.setdefault("linked_user_name", name)
        return enriched

    def _enrich_group_ticket(self, item: dict) -> dict:
        group_id = self._int_value(item.get("groups_id"))
        if not group_id:
            return item

        enriched = dict(item)
        enriched.setdefault("linked_type_label", self._ticket_actor_type_label(item.get("type")))
        name = self._get_item_display_name("Group", group_id)
        if name:
            enriched.setdefault("linked_group_name", name)
        return enriched

    def _get_item_display_name(self, itemtype: str, item_id: int) -> str:
        cache_key = (itemtype, item_id)
        if cache_key in self._item_name_cache:
            return self._item_name_cache[cache_key]

        try:
            item = self.glpi_client.get_item(itemtype, item_id)
        except GLPIClientError:
            logger.warning(
                "ticket_notification_linked_item_read_failed",
                extra={"itemtype": itemtype, "item_id": item_id},
            )
            self._item_name_cache[cache_key] = ""
            return ""

        name = self._display_name_from_item(item)
        self._item_name_cache[cache_key] = name
        return name

    @staticmethod
    def _display_name_from_item(item: dict) -> str:
        full_name = " ".join(
            part.strip()
            for part in (
                str(item.get("firstname") or ""),
                str(item.get("realname") or ""),
            )
            if part and part.strip()
        ).strip()
        if full_name:
            return full_name
        for field in ("completename", "name", "login"):
            value = item.get(field)
            if value not in (None, ""):
                return str(value).strip()
        return ""

    @staticmethod
    def _ticket_actor_type_label(value) -> str:
        return {
            "1": "solicitante",
            "2": "responsável pelo atendimento",
            "3": "observador",
        }.get(str(value or "").strip(), "")

    @staticmethod
    def _int_value(value) -> int:
        try:
            return int(value or 0)
        except (TypeError, ValueError):
            return 0
