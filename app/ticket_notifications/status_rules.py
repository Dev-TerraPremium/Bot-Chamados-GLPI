from __future__ import annotations

import unicodedata
from typing import Any


DEFAULT_ACTIVE_STATUS_TOKENS = {
    "1",
    "2",
    "3",
    "4",
    "aberto",
    "ativo",
    "novo",
    "em atendimento",
    "processando",
    "processando atribuido",
    "processando planejado",
    "planejado",
    "pendente",
    "aguardando",
    "aguardando acao",
}

DEFAULT_TERMINAL_STATUS_TOKENS = {
    "5",
    "6",
    "solucionado",
    "solucionada",
    "resolvido",
    "resolvida",
    "fechado",
    "fechada",
    "encerrado",
    "encerrada",
    "deletado",
    "deletada",
    "excluido",
    "excluida",
    "cancelado",
    "cancelada",
    "arquivado",
    "arquivada",
}


def is_monitorable_ticket(
    ticket: dict[str, Any] | None,
    configured_terminal_statuses: str = "",
) -> bool:
    if not ticket or is_deleted_ticket(ticket):
        return False
    return is_monitorable_status(ticket.get("status"), configured_terminal_statuses)


def is_terminal_ticket(
    ticket: dict[str, Any] | None,
    configured_terminal_statuses: str = "",
) -> bool:
    if not ticket:
        return False
    return is_deleted_ticket(ticket) or is_terminal_status(
        ticket.get("status"),
        configured_terminal_statuses,
    )


def is_monitorable_status(value: Any, configured_terminal_statuses: str = "") -> bool:
    token = normalize_status_token(value)
    if not token or is_terminal_status(token, configured_terminal_statuses):
        return False
    return token in DEFAULT_ACTIVE_STATUS_TOKENS


def is_terminal_status(value: Any, configured_terminal_statuses: str = "") -> bool:
    token = normalize_status_token(value)
    if not token:
        return False
    return token in DEFAULT_TERMINAL_STATUS_TOKENS or token in _configured_status_tokens(
        configured_terminal_statuses
    )


def is_deleted_ticket(ticket: dict[str, Any]) -> bool:
    return any(
        _truthy(ticket.get(field))
        for field in ("is_deleted", "is_deleted_ticket", "deleted", "is_removed")
    )


def normalize_status_token(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    text = unicodedata.normalize("NFKD", text)
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = text.casefold()
    text = text.replace("_", " ").replace("-", " ")
    return " ".join(text.split())


def _configured_status_tokens(value: str) -> set[str]:
    return {
        token
        for token in (normalize_status_token(item) for item in value.split(","))
        if token
    }


def _truthy(value: Any) -> bool:
    return normalize_status_token(value) in {"1", "true", "sim", "yes", "y"}
