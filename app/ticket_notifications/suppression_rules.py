from __future__ import annotations

import unicodedata

from app.ticket_notifications.models import TicketEvent


class TicketNotificationSuppressionRules:
    def __init__(self, disabled_event_types: str = "") -> None:
        self.disabled_event_types = self._split(disabled_event_types)

    def disabled_key(self, event: TicketEvent) -> str:
        event_type = str(event.event_type or "").strip()
        if event_type in self.disabled_event_types:
            return event_type
        if (
            "ticket_group_responsible_linked" in self.disabled_event_types
            and self._is_responsible_group_link(event)
        ):
            return "ticket_group_responsible_linked"
        return ""

    def is_disabled(self, event: TicketEvent) -> bool:
        return bool(self.disabled_key(event))

    @classmethod
    def _split(cls, value: str) -> set[str]:
        return {
            item.strip()
            for item in str(value or "").split(",")
            if item.strip()
        }

    @classmethod
    def _is_responsible_group_link(cls, event: TicketEvent) -> bool:
        if event.event_type != "ticket_group_changed":
            return False
        payload = event.raw_payload or {}
        linked_type = str(payload.get("type") or "").strip()
        if linked_type == "2":
            return True
        role_label = cls._normalize(str(payload.get("linked_type_label") or ""))
        return role_label == "responsavel pelo atendimento"

    @staticmethod
    def _normalize(value: str) -> str:
        without_accents = "".join(
            char
            for char in unicodedata.normalize("NFKD", value)
            if not unicodedata.combining(char)
        )
        return " ".join(without_accents.casefold().split())
