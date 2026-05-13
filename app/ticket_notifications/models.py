from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class WatchedTicket:
    ticket_id: int
    requester_phone: str
    requester_name: str
    requester_login: str
    category_name: str
    title: str
    location: str
    created_at: str
    channel: str = "whatsapp"
    channel_identifier: str = ""
    notification_status: str = "watching"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WatchedTicket":
        return cls(
            ticket_id=int(data["ticket_id"]),
            requester_phone=str(data.get("requester_phone") or ""),
            requester_name=str(data.get("requester_name") or ""),
            requester_login=str(data.get("requester_login") or ""),
            category_name=str(data.get("category_name") or ""),
            title=str(data.get("title") or ""),
            location=str(data.get("location") or ""),
            created_at=str(data.get("created_at") or ""),
            channel=str(data.get("channel") or "whatsapp"),
            channel_identifier=str(
                data.get("channel_identifier")
                or data.get("requester_channel_identifier")
                or data.get("requester_phone")
                or ""
            ),
            notification_status=str(data.get("notification_status") or "watching"),
        )


@dataclass(frozen=True, slots=True)
class TicketEvent:
    ticket_id: int
    event_type: str
    source_itemtype: str
    source_id: str
    occurred_at: str
    is_private: bool
    actor: str
    old_value: str
    new_value: str
    raw_payload: dict[str, Any] = field(default_factory=dict)
    notification_status: str = "pending"

    @property
    def signature(self) -> str:
        parts = (
            str(self.ticket_id),
            self.event_type,
            self.source_itemtype,
            str(self.source_id),
            self.occurred_at,
            self.old_value,
            self.new_value,
        )
        return "|".join(parts)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class TicketActivitySnapshot:
    ticket_id: int
    ticket: dict[str, Any]
    related_items: dict[str, list[dict[str, Any]]]
