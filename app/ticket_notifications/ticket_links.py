from __future__ import annotations


def build_ticket_public_url(template: str, ticket_id: int | str) -> str:
    """Build a user-facing GLPI ticket URL from a configurable template."""
    clean_template = (template or "").strip()
    if not clean_template:
        return ""

    ticket_value = str(ticket_id).strip()
    if not ticket_value:
        return ""

    if "{ticket_id}" in clean_template:
        return clean_template.format(ticket_id=ticket_value)

    separator = "&" if "?" in clean_template else "?"
    return f"{clean_template}{separator}id={ticket_value}"
