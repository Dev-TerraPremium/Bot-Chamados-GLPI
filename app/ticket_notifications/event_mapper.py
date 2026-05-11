from __future__ import annotations

import re
from html import unescape
from typing import Any

from app.ticket_notifications.models import TicketActivitySnapshot, TicketEvent


STATUS_LABELS = {
    "1": "novo",
    "2": "em atendimento",
    "3": "planejado",
    "4": "pendente",
    "5": "solucionado",
    "6": "fechado",
}

TICKET_FIELDS = {
    "status": "ticket_status_changed",
    "priority": "ticket_priority_changed",
    "urgency": "ticket_urgency_changed",
    "impact": "ticket_impact_changed",
    "itilcategories_id": "ticket_category_changed",
    "locations_id": "ticket_location_changed",
    "name": "ticket_title_changed",
    "content": "ticket_description_changed",
    "entities_id": "ticket_entity_changed",
    "time_to_resolve": "ticket_sla_resolve_changed",
    "time_to_own": "ticket_sla_own_changed",
    "takeintoaccountdate": "ticket_taken_changed",
    "solvedate": "ticket_solved_changed",
    "closedate": "ticket_closed_changed",
    "begin_waiting_date": "ticket_waiting_changed",
}

RELATED_EVENT_TYPES = {
    "ITILFollowup": "followup_added",
    "ITILSolution": "solution_added",
    "TicketTask": "task_added",
    "TicketValidation": "validation_changed",
    "Document_Item": "document_changed",
    "Ticket_User": "ticket_user_changed",
    "Group_Ticket": "ticket_group_changed",
}


class TicketEventMapper:
    def events_from_snapshot(
        self,
        snapshot: TicketActivitySnapshot,
        previous_snapshot: dict | None,
    ) -> list[TicketEvent]:
        events: list[TicketEvent] = []
        if previous_snapshot:
            events.extend(self._ticket_field_events(snapshot, previous_snapshot))
        events.extend(self._related_item_events(snapshot))
        return events

    def comparable_snapshot(self, snapshot: TicketActivitySnapshot) -> dict[str, Any]:
        return {
            "ticket": {
                field: self._stringify(snapshot.ticket.get(field))
                for field in TICKET_FIELDS
            },
            "related_signatures": {
                itemtype: [
                    self._related_signature(itemtype, item)
                    for item in snapshot.related_items.get(itemtype, [])
                ]
                for itemtype in RELATED_EVENT_TYPES
            },
        }

    def _ticket_field_events(
        self,
        snapshot: TicketActivitySnapshot,
        previous_snapshot: dict,
    ) -> list[TicketEvent]:
        previous_ticket = previous_snapshot.get("ticket") or {}
        events: list[TicketEvent] = []
        for field, event_type in TICKET_FIELDS.items():
            old_value = self._stringify(previous_ticket.get(field))
            new_value = self._stringify(snapshot.ticket.get(field))
            if old_value == new_value:
                continue
            events.append(
                TicketEvent(
                    ticket_id=snapshot.ticket_id,
                    event_type=event_type,
                    source_itemtype="Ticket",
                    source_id=field,
                    occurred_at=self._occurred_at(snapshot.ticket),
                    is_private=False,
                    actor=self._actor(snapshot.ticket),
                    old_value=self._display_value(field, old_value),
                    new_value=self._display_value(field, new_value),
                    raw_payload={"field": field, "ticket": snapshot.ticket},
                )
            )
        return events

    def _related_item_events(self, snapshot: TicketActivitySnapshot) -> list[TicketEvent]:
        events: list[TicketEvent] = []
        for itemtype, event_type in RELATED_EVENT_TYPES.items():
            for item in snapshot.related_items.get(itemtype, []):
                source_id = self._item_id(item)
                events.append(
                    TicketEvent(
                        ticket_id=snapshot.ticket_id,
                        event_type=event_type,
                        source_itemtype=itemtype,
                        source_id=source_id,
                        occurred_at=self._occurred_at(item),
                        is_private=self._is_private(item),
                        actor=self._actor(item),
                        old_value="",
                        new_value=self._content(item),
                        raw_payload=item,
                    )
                )
        return events

    def _related_signature(self, itemtype: str, item: dict[str, Any]) -> str:
        return "|".join(
            [
                itemtype,
                self._item_id(item),
                self._occurred_at(item),
                self._content(item),
            ]
        )

    @staticmethod
    def _item_id(item: dict[str, Any]) -> str:
        return str(item.get("id") or item.get("items_id") or item.get("documents_id") or "")

    @staticmethod
    def _occurred_at(item: dict[str, Any]) -> str:
        for field in ("date_creation", "date", "date_mod", "solvedate", "closedate"):
            value = item.get(field)
            if value:
                return str(value)
        return ""

    @staticmethod
    def _actor(item: dict[str, Any]) -> str:
        for field in ("users_id", "users_id_editor", "users_id_lastupdater"):
            value = item.get(field)
            if value:
                return str(value)
        return ""

    @staticmethod
    def _is_private(item: dict[str, Any]) -> bool:
        return str(item.get("is_private") or "0") in {"1", "true", "True"}

    @staticmethod
    def _content(item: dict[str, Any]) -> str:
        for field in ("content", "comment", "name", "filename", "users_id", "groups_id"):
            value = item.get(field)
            if value:
                return TicketEventMapper._strip_markup(str(value))
        return ""

    @staticmethod
    def _display_value(field: str, value: str) -> str:
        if field == "status":
            return STATUS_LABELS.get(value, value)
        if field == "content":
            return TicketEventMapper._strip_markup(value)
        return value

    @staticmethod
    def _strip_markup(value: str) -> str:
        value = unescape(value)
        value = re.sub(r"<br\s*/?>", "\n", value, flags=re.IGNORECASE)
        value = re.sub(r"</p>", "\n", value, flags=re.IGNORECASE)
        value = re.sub(r"<[^>]+>", "", value)
        return re.sub(r"\s+", " ", value).strip()

    @staticmethod
    def _stringify(value: Any) -> str:
        if value is None:
            return ""
        return str(value).strip()
