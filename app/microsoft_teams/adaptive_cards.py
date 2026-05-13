from __future__ import annotations

from app.ticket_notifications.ticket_links import build_ticket_public_url


class TeamsAdaptiveCardRenderer:
    CONTENT_TYPE = "application/vnd.microsoft.card.adaptive"

    def __init__(self, ticket_url_template: str = "") -> None:
        self.ticket_url_template = ticket_url_template

    def ticket_opened_card(self, created_ticket: dict) -> dict:
        ticket_id = created_ticket.get("ticket_number")
        return self._ticket_card(
            title=f"Chamado #{ticket_id} aberto com sucesso",
            subtitle="Sua solicitação já está com a equipe técnica.",
            ticket_id=ticket_id,
            facts={
                "Categoria": str(
                    created_ticket.get("category")
                    or created_ticket.get("category_name")
                    or "Suporte TI"
                ),
                "Prioridade": str(created_ticket.get("severity") or "Não informada"),
            },
        )

    def ticket_update_card(self, ticket_id: int, message: str) -> dict:
        return self._ticket_card(
            title=f"Atualização no chamado #{ticket_id}",
            subtitle=message,
            ticket_id=ticket_id,
            facts={},
        )

    def attachment(self, card: dict) -> dict:
        return {
            "contentType": self.CONTENT_TYPE,
            "content": card,
        }

    def _ticket_card(
        self,
        *,
        title: str,
        subtitle: str,
        ticket_id: int | str,
        facts: dict[str, str],
    ) -> dict:
        body = [
            {
                "type": "TextBlock",
                "text": title,
                "weight": "Bolder",
                "size": "Medium",
                "wrap": True,
            },
            {"type": "TextBlock", "text": subtitle, "wrap": True},
        ]
        if facts:
            body.append(
                {
                    "type": "FactSet",
                    "facts": [
                        {"title": f"{title}:", "value": value}
                        for title, value in facts.items()
                    ],
                }
            )

        actions = []
        ticket_url = build_ticket_public_url(self.ticket_url_template, ticket_id)
        if ticket_url:
            actions.append(
                {
                    "type": "Action.OpenUrl",
                    "title": "Ver chamado no GLPI",
                    "url": ticket_url,
                }
            )

        return {
            "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
            "type": "AdaptiveCard",
            "version": "1.4",
            "body": body,
            "actions": actions,
        }
