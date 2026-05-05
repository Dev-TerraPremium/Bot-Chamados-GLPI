from dataclasses import asdict, dataclass, field


@dataclass(slots=True)
class TicketDraft:
    requester_name: str
    requester_login: str
    requester_email: str
    glpi_user_id: int
    channel: str
    opening_mode: str
    category_id: int
    category_name: str
    description: str
    impact_id: int
    impact_label: str
    severity: str
    location: str
    evidence: str
    title: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(slots=True)
class TicketFollowup:
    ticket_number: int
    user_id: int
    content: str
    created_at: str

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "TicketFollowup":
        return cls(
            ticket_number=int(data["ticket_number"]),
            user_id=int(data["user_id"]),
            content=str(data["content"]),
            created_at=str(data["created_at"]),
        )


@dataclass(slots=True)
class TicketCreated:
    ticket_number: int
    title: str
    status: str
    severity: str
    description: str
    category_name: str
    requester_login: str
    glpi_user_id: int
    channel: str
    location: str
    impact_label: str
    evidence: str
    opening_mode: str
    created_at: str
    followups: list[TicketFollowup] = field(default_factory=list)

    def to_dict(self) -> dict:
        data = asdict(self)
        data["followups"] = [followup.to_dict() for followup in self.followups]
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "TicketCreated":
        followups = [
            TicketFollowup.from_dict(followup)
            for followup in data.get("followups", [])
        ]
        return cls(
            ticket_number=int(data["ticket_number"]),
            title=str(data["title"]),
            status=str(data["status"]),
            severity=str(data["severity"]),
            description=str(data["description"]),
            category_name=str(data["category_name"]),
            requester_login=str(data["requester_login"]),
            glpi_user_id=int(data["glpi_user_id"]),
            channel=str(data["channel"]),
            location=str(data["location"]),
            impact_label=str(data["impact_label"]),
            evidence=str(data["evidence"]),
            opening_mode=str(data["opening_mode"]),
            created_at=str(data["created_at"]),
            followups=followups,
        )


@dataclass(frozen=True, slots=True)
class TicketSummary:
    requester: str
    channel: str
    category: str
    description: str
    impact: str
    severity: str
    location: str
    evidence: str
    suggested_title: str

    def to_dict(self) -> dict:
        return asdict(self)
