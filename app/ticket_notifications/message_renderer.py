from __future__ import annotations

from app.ticket_notifications.models import TicketEvent, WatchedTicket


class TicketNotificationMessageRenderer:
    def render_user_message(self, watched_ticket: WatchedTicket, event: TicketEvent) -> str:
        ticket_label = f"#{watched_ticket.ticket_id}"
        requester = watched_ticket.requester_name.split()[0] if watched_ticket.requester_name else ""
        greeting = f"{requester}, " if requester else ""

        if event.event_type == "followup_added":
            return self._sentence(
                greeting,
                f"o chamado {ticket_label} recebeu uma nova resposta: {event.new_value}",
            )
        if event.event_type == "solution_added":
            return self._sentence(
                greeting,
                f"foi registrada uma solucao no chamado {ticket_label}: {event.new_value}",
            )
        if event.event_type == "task_added":
            return self._sentence(
                greeting,
                f"houve uma atividade registrada no chamado {ticket_label}: {event.new_value}",
            )
        if event.event_type == "document_changed":
            detail = event.new_value or "um anexo foi atualizado"
            return self._sentence(greeting, f"o chamado {ticket_label} teve anexo atualizado: {detail}")
        if event.event_type == "validation_changed":
            detail = event.new_value or "a validacao foi atualizada"
            return self._sentence(greeting, f"a validacao do chamado {ticket_label} foi atualizada: {detail}")
        if event.event_type == "ticket_user_changed":
            return self._sentence(greeting, f"as pessoas vinculadas ao chamado {ticket_label} foram atualizadas.")
        if event.event_type == "ticket_group_changed":
            return self._sentence(greeting, f"o grupo responsavel pelo chamado {ticket_label} foi atualizado.")
        if event.event_type in {"ticket_solved_changed", "ticket_closed_changed"}:
            return self._sentence(greeting, f"o chamado {ticket_label} avancou para uma etapa de conclusao.")
        if event.event_type == "ticket_status_changed":
            return self._sentence(
                greeting,
                f"o status do chamado {ticket_label} mudou de {event.old_value or 'nao informado'} para {event.new_value or 'nao informado'}.",
            )
        if event.event_type.startswith("ticket_"):
            return self._sentence(greeting, f"o chamado {ticket_label} recebeu uma atualizacao de estado.")
        return self._sentence(greeting, f"o chamado {ticket_label} recebeu uma nova atualizacao.")

    def render_internal_ticket_opened(
        self,
        watched_ticket: WatchedTicket,
        created_ticket: dict,
    ) -> str:
        return (
            f"Um novo chamado foi aberto pelo bot: #{watched_ticket.ticket_id}. "
            f"Solicitante: {watched_ticket.requester_name or watched_ticket.requester_login}. "
            f"Categoria: {watched_ticket.category_name or created_ticket.get('category_name') or 'nao informada'}. "
            f"Resumo: {created_ticket.get('description') or watched_ticket.title or 'sem resumo informado'}."
        )

    @staticmethod
    def _sentence(greeting: str, content: str) -> str:
        text = (greeting + content).strip()
        if not text.endswith((".", "!", "?")):
            text += "."
        return text
