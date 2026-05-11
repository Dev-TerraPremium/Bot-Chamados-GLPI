from __future__ import annotations

import hashlib
from typing import Any

from app.ticket_notifications.models import TicketEvent, WatchedTicket
from app.ticket_notifications.ticket_links import build_ticket_public_url


FIELD_LABELS = {
    "status": "status",
    "priority": "prioridade",
    "urgency": "urgência",
    "impact": "impacto",
    "itilcategories_id": "categoria",
    "locations_id": "localidade",
    "name": "título",
    "content": "descrição",
    "entities_id": "entidade",
    "time_to_resolve": "prazo de solução",
    "time_to_own": "prazo para assumir",
    "takeintoaccountdate": "data de atendimento",
    "solvedate": "data de solução",
    "closedate": "data de fechamento",
    "begin_waiting_date": "início da pendência",
}

FIELD_ARTICLES = {
    "status": "o",
    "priority": "a",
    "urgency": "a",
    "impact": "o",
    "itilcategories_id": "a",
    "locations_id": "a",
    "name": "o",
    "content": "a",
    "entities_id": "a",
    "time_to_resolve": "o",
    "time_to_own": "o",
    "takeintoaccountdate": "a",
    "solvedate": "a",
    "closedate": "a",
    "begin_waiting_date": "o",
}


class TicketNotificationMessageRenderer:
    def __init__(self, ticket_url_template: str = "") -> None:
        self.ticket_url_template = ticket_url_template

    def render_user_message(self, watched_ticket: WatchedTicket, event: TicketEvent) -> str:
        ticket_label = f"#{watched_ticket.ticket_id}"
        ticket_url = build_ticket_public_url(self.ticket_url_template, watched_ticket.ticket_id)
        detail = self._event_detail(event)
        opener = self._notification_opener(watched_ticket, event, ticket_label)
        message = self._sentence(f"{opener} {detail}".strip())

        if ticket_url:
            message += f"\n\n🔗 *Acompanhar chamado:* {ticket_url}"
        return message

    def render_internal_ticket_opened(
        self,
        watched_ticket: WatchedTicket,
        created_ticket: dict,
    ) -> str:
        ticket_label = f"#{watched_ticket.ticket_id}"
        ticket_url = build_ticket_public_url(self.ticket_url_template, watched_ticket.ticket_id)
        requester = watched_ticket.requester_name or watched_ticket.requester_login or "solicitante não informado"
        category = watched_ticket.category_name or created_ticket.get("category_name") or "não informada"
        summary = created_ticket.get("description") or watched_ticket.title or "sem resumo informado"

        message = (
            f"Um novo chamado foi aberto pelo bot: *{ticket_label}*.\n\n"
            f"Solicitante: *{requester}*\n"
            f"Categoria: *{category}*\n"
            f"Resumo: {summary}."
        )
        if ticket_url:
            message += f"\n\n🔗 *Acessar chamado:* {ticket_url}"
        return message

    def render_internal_event_message(
        self,
        watched_ticket: WatchedTicket,
        event: TicketEvent,
    ) -> str:
        ticket_label = f"#{watched_ticket.ticket_id}"
        ticket_url = build_ticket_public_url(self.ticket_url_template, watched_ticket.ticket_id)
        requester = watched_ticket.requester_name or watched_ticket.requester_login or "solicitante não informado"
        detail = self._event_detail(event)

        message = self._sentence(
            f"Atualização do chamado *{ticket_label}* aberto por *{requester}*: "
            f"{detail}"
        )
        if ticket_url:
            message += f"\n\n🔗 *Acessar chamado:* {ticket_url}"
        return message

    def render_error_alert_message(
        self,
        *,
        reason: str,
        ticket_id: int | None = None,
        detail: str = "",
    ) -> str:
        ticket_part = f" no chamado *#{ticket_id}*" if ticket_id else ""
        message = f"Falha no monitoramento de chamados{ticket_part}: *{reason}*."
        if detail:
            message += f"\n\nDetalhe: {detail}"
        return message

    def _notification_opener(
        self,
        watched_ticket: WatchedTicket,
        event: TicketEvent,
        ticket_label: str,
    ) -> str:
        first_name = self._first_name(watched_ticket.requester_name)
        variants = [
            f"Atualização do chamado *{ticket_label}*:",
            f"Houve uma nova atualização no chamado *{ticket_label}*:",
            f"O chamado *{ticket_label}* foi atualizado:",
            f"Passando uma atualização do chamado *{ticket_label}*:",
        ]
        if first_name:
            variants.append(f"{first_name}, chegou uma atualização do chamado *{ticket_label}*:")
        return variants[self._stable_index(event.signature, len(variants))]

    def _event_detail(self, event: TicketEvent) -> str:
        if event.event_type == "followup_added":
            return f"o técnico registrou uma resposta: {self._quoted_detail(event.new_value)}"
        if event.event_type == "solution_added":
            return f"foi registrada uma *solução*: {self._quoted_detail(event.new_value)}"
        if event.event_type == "task_added":
            return f"houve uma *atividade* registrada: {self._quoted_detail(event.new_value)}"
        if event.event_type == "document_changed":
            detail = self._clean_detail(event.new_value) or "um anexo foi atualizado"
            return f"um *anexo* foi atualizado: {detail}"
        if event.event_type == "validation_changed":
            detail = self._clean_detail(event.new_value) or "a validação foi atualizada"
            return f"a *validação* foi atualizada: {detail}"
        if event.event_type == "ticket_user_changed":
            person = self._linked_person_detail(event)
            return f"as *pessoas vinculadas* foram atualizadas: {person}" if person else "as *pessoas vinculadas* foram atualizadas"
        if event.event_type == "ticket_group_changed":
            group = self._linked_group_detail(event)
            return f"o *grupo responsável* foi atualizado: {group}" if group else "o *grupo responsável* foi atualizado"
        if event.event_type in {"ticket_solved_changed", "ticket_closed_changed"}:
            return self._changed_field_detail(event, default_field="etapa de conclusão")
        if event.event_type.startswith("ticket_"):
            return self._changed_field_detail(event)
        return "houve uma nova atualização"

    def _changed_field_detail(self, event: TicketEvent, default_field: str = "informação") -> str:
        field = self._field_label(event) or default_field
        old_value = self._clean_detail(event.old_value) or "não informado"
        new_value = self._clean_detail(event.new_value) or "não informado"

        if event.old_value or event.new_value:
            return f"{self._field_article(event, field)} *{field}* mudou de *{old_value}* para *{new_value}*"
        return f"{self._field_article(event, field)} *{field}* foi atualizada"

    def _field_label(self, event: TicketEvent) -> str:
        field = str((event.raw_payload or {}).get("field") or "")
        if field:
            return FIELD_LABELS.get(field, field)

        event_to_field = {
            "ticket_status_changed": "status",
            "ticket_priority_changed": "prioridade",
            "ticket_urgency_changed": "urgência",
            "ticket_impact_changed": "impacto",
            "ticket_category_changed": "categoria",
            "ticket_location_changed": "localidade",
            "ticket_title_changed": "título",
            "ticket_description_changed": "descrição",
            "ticket_entity_changed": "entidade",
            "ticket_sla_resolve_changed": "prazo de solução",
            "ticket_sla_own_changed": "prazo para assumir",
            "ticket_taken_changed": "data de atendimento",
            "ticket_solved_changed": "solução",
            "ticket_closed_changed": "fechamento",
            "ticket_waiting_changed": "pendência",
        }
        return event_to_field.get(event.event_type, "")

    def _field_article(self, event: TicketEvent, field_label: str) -> str:
        field = str((event.raw_payload or {}).get("field") or "")
        if field:
            return FIELD_ARTICLES.get(field, "a")

        if field_label in {
            "status",
            "impacto",
            "título",
            "prazo de solução",
            "prazo para assumir",
            "fechamento",
        }:
            return "o"
        return "a"

    def _linked_person_detail(self, event: TicketEvent) -> str:
        payload = event.raw_payload or {}
        name = self._first_present(payload, ("name", "realname", "firstname", "comment", "content"))
        user_id = self._first_present(payload, ("users_id", "users_id_editor", "users_id_lastupdater"))
        link_type = self._first_present(payload, ("type", "use_notification"))

        if name:
            return name
        if user_id and link_type:
            return f"usuário ID {user_id}, vínculo {link_type}"
        if user_id:
            return f"usuário ID {user_id}"
        return self._clean_detail(event.new_value)

    def _linked_group_detail(self, event: TicketEvent) -> str:
        payload = event.raw_payload or {}
        name = self._first_present(payload, ("name", "comment", "content"))
        group_id = self._first_present(payload, ("groups_id", "id"))
        link_type = self._first_present(payload, ("type",))

        if name:
            return name
        if group_id and link_type:
            return f"grupo ID {group_id}, vínculo {link_type}"
        if group_id:
            return f"grupo ID {group_id}"
        return self._clean_detail(event.new_value)

    @staticmethod
    def _first_present(payload: dict[str, Any], keys: tuple[str, ...]) -> str:
        for key in keys:
            value = payload.get(key)
            if value not in (None, ""):
                return str(value).strip()
        return ""

    @staticmethod
    def _first_name(full_name: str) -> str:
        return (full_name or "").strip().split(" ")[0] if full_name else ""

    @staticmethod
    def _stable_index(seed: str, modulo: int) -> int:
        digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()
        return int(digest[:8], 16) % modulo

    @staticmethod
    def _clean_detail(value: str) -> str:
        return (value or "").strip()

    @classmethod
    def _quoted_detail(cls, value: str) -> str:
        detail = cls._clean_detail(value)
        return f"“{detail}”" if detail else "sem detalhe informado"

    @staticmethod
    def _sentence(text: str) -> str:
        text = text.strip()
        if not text.endswith((".", "!", "?", ".”", "!”", "?”")):
            text += "."
        return text
