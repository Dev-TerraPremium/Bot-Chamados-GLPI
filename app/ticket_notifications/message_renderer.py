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
        detail = self._event_detail(event)
        opener = self._notification_opener(watched_ticket, event, ticket_label)
        message = self._sentence(f"{opener}\n\n{detail}".strip())
        return self._with_ticket_link(message, watched_ticket.ticket_id, "Ver chamado no GLPI")

    def render_internal_ticket_opened(
        self,
        watched_ticket: WatchedTicket,
        created_ticket: dict,
    ) -> str:
        ticket_label = f"#{watched_ticket.ticket_id}"
        requester = (
            watched_ticket.requester_name
            or watched_ticket.requester_login
            or "solicitante não informado"
        )
        category = watched_ticket.category_name or created_ticket.get("category_name") or "não informada"
        summary = created_ticket.get("description") or watched_ticket.title or "sem resumo informado"

        message = (
            f"🆕 Novo chamado aberto pelo bot: *{ticket_label}*\n\n"
            f"👤 Solicitante: *{requester}*\n"
            f"🏷️ Categoria: *{category}*\n"
            f"📝 Resumo: {summary}"
        )
        return self._with_ticket_link(message, watched_ticket.ticket_id, "Abrir chamado no GLPI")

    def render_internal_event_message(
        self,
        watched_ticket: WatchedTicket,
        event: TicketEvent,
    ) -> str:
        ticket_label = f"#{watched_ticket.ticket_id}"
        requester = (
            watched_ticket.requester_name
            or watched_ticket.requester_login
            or "solicitante não informado"
        )
        detail = self._event_detail(event)

        message = self._sentence(
            f"🔔 Atualização no chamado *{ticket_label}* de *{requester}*:\n\n{detail}"
        )
        return self._with_ticket_link(message, watched_ticket.ticket_id, "Abrir chamado no GLPI")

    def render_error_alert_message(
        self,
        *,
        reason: str,
        ticket_id: int | None = None,
        detail: str = "",
    ) -> str:
        ticket_part = f" no chamado *#{ticket_id}*" if ticket_id else ""
        message = f"⚠️ Falha no monitoramento de chamados{ticket_part}: *{reason}*."
        if detail:
            message += f"\n\nDetalhe técnico: {detail}"
        if ticket_id:
            return self._with_ticket_link(message, ticket_id, "Abrir chamado no GLPI")
        return message

    def _notification_opener(
        self,
        watched_ticket: WatchedTicket,
        event: TicketEvent,
        ticket_label: str,
    ) -> str:
        first_name = self._first_name(watched_ticket.requester_name)
        variants = [
            f"🔔 Atualização no chamado *{ticket_label}*",
            f"📌 Seu chamado *{ticket_label}* teve uma movimentação",
            f"✅ Tenho uma novidade sobre o chamado *{ticket_label}*",
            f"🛠️ O chamado *{ticket_label}* foi atualizado",
        ]
        if first_name:
            variants.append(f"🔔 {first_name}, chegou uma atualização no chamado *{ticket_label}*")
        return variants[self._stable_index(event.signature, len(variants))]

    def _event_detail(self, event: TicketEvent) -> str:
        if event.event_type == "followup_added":
            return f"A equipe registrou uma nova resposta: {self._quoted_detail(event.new_value)}"
        if event.event_type == "solution_added":
            return f"Foi registrada uma proposta de solução: {self._quoted_detail(event.new_value)}"
        if event.event_type == "task_added":
            return f"Uma atividade foi registrada no atendimento: {self._quoted_detail(event.new_value)}"
        if event.event_type == "document_changed":
            detail = self._clean_detail(event.new_value) or "um anexo foi atualizado"
            return f"Um anexo do chamado foi atualizado: {detail}"
        if event.event_type == "validation_changed":
            detail = self._clean_detail(event.new_value) or "a validação foi atualizada"
            return f"A validação do chamado foi atualizada: {detail}"
        if event.event_type == "ticket_user_changed":
            person = self._linked_person_detail(event)
            return person or "As pessoas vinculadas ao chamado foram atualizadas."
        if event.event_type == "ticket_group_changed":
            group = self._linked_group_detail(event)
            return group or "O grupo responsável pelo chamado foi atualizado."
        if event.event_type in {"ticket_solved_changed", "ticket_closed_changed"}:
            return self._changed_field_detail(event, default_field="etapa de conclusão")
        if event.event_type.startswith("ticket_"):
            return self._changed_field_detail(event)
        return "Houve uma nova atualização no chamado."

    def _changed_field_detail(self, event: TicketEvent, default_field: str = "informação") -> str:
        field = self._field_label(event) or default_field
        old_value = self._clean_detail(event.old_value) or "não informado"
        new_value = self._clean_detail(event.new_value) or "não informado"

        if event.old_value or event.new_value:
            return (
                f"{self._field_article(event, field).capitalize()} *{field}* mudou "
                f"de *{old_value}* → *{new_value}*"
            )
        return f"{self._field_article(event, field).capitalize()} *{field}* foi atualizada"

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
        name = self._first_present(
            payload,
            (
                "linked_user_name",
                "user_name",
                "name",
                "realname",
                "firstname",
                "comment",
                "content",
            ),
        )
        user_id = self._first_present(payload, ("users_id", "users_id_editor", "users_id_lastupdater"))
        role = self._first_present(payload, ("linked_type_label",)) or self._ticket_actor_type_label(
            self._first_present(payload, ("type",))
        )
        notification_hint = self._notification_hint(payload)

        if name and role:
            return f"A pessoa *{name}* foi vinculada ao chamado como *{role}*. {notification_hint}".strip()
        if name:
            return f"A pessoa *{name}* foi vinculada ao chamado. {notification_hint}".strip()
        if user_id and role:
            return f"Uma pessoa foi vinculada ao chamado como *{role}*. {notification_hint}".strip()
        if user_id:
            return "Uma pessoa foi vinculada ao chamado."
        return self._clean_detail(event.new_value)

    def _linked_group_detail(self, event: TicketEvent) -> str:
        payload = event.raw_payload or {}
        name = self._first_present(payload, ("linked_group_name", "group_name", "name", "comment", "content"))
        group_id = self._first_present(payload, ("groups_id", "id"))
        role = self._first_present(payload, ("linked_type_label",)) or self._ticket_actor_type_label(
            self._first_present(payload, ("type",))
        )

        if name and role:
            return f"O grupo *{name}* foi vinculado ao chamado como *{role}*."
        if name:
            return f"O grupo *{name}* foi vinculado ao chamado."
        if group_id and role:
            return f"Um grupo foi vinculado ao chamado como *{role}*."
        if group_id:
            return "Um grupo foi vinculado ao chamado."
        return self._clean_detail(event.new_value)

    def _with_ticket_link(self, message: str, ticket_id: int, label: str) -> str:
        ticket_url = build_ticket_public_url(self.ticket_url_template, ticket_id)
        if not ticket_url:
            return message
        return f"{message}\n\n🔗 *{label}:* {ticket_url}"

    @staticmethod
    def _notification_hint(payload: dict[str, Any]) -> str:
        value = str(payload.get("use_notification") or "").strip().lower()
        if value in {"1", "true", "yes"}:
            return "Ela também receberá as notificações do GLPI."
        if value in {"0", "false", "no"}:
            return "Ela não receberá notificações automáticas do GLPI."
        return ""

    @staticmethod
    def _ticket_actor_type_label(value: str) -> str:
        return {
            "1": "solicitante",
            "2": "responsável pelo atendimento",
            "3": "observador",
        }.get(str(value or "").strip(), "")

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
        if not text.endswith((".", "!", "?", ".“", "!”", "?”", ".”")):
            text += "."
        return text
