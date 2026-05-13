from __future__ import annotations


STATUS_LABELS = {
    "1": "novo",
    "2": "em atendimento",
    "3": "planejado",
    "4": "pendente",
    "5": "solucionado",
    "6": "fechado",
}

LEVEL_LABELS = {
    "1": "Muito baixa",
    "2": "Baixa",
    "3": "Média",
    "4": "Alta",
    "5": "Muito alta",
    "6": "Crítica",
}


def display_ticket_field_value(field: str, value: str) -> str:
    clean_value = str(value or "").strip()
    if not clean_value:
        return ""
    if field == "status":
        return STATUS_LABELS.get(clean_value, clean_value)
    if field in {"priority", "urgency"}:
        return LEVEL_LABELS.get(clean_value, clean_value)
    if field == "impact":
        label = LEVEL_LABELS.get(clean_value, clean_value)
        return _masculine_level_label(label)
    return clean_value


def _masculine_level_label(label: str) -> str:
    return {
        "Muito baixa": "Muito baixo",
        "Baixa": "Baixo",
        "Média": "Médio",
        "Alta": "Alto",
        "Muito alta": "Muito alto",
    }.get(label, label)
