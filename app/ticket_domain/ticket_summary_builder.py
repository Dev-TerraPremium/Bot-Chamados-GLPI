from app.ticket_domain.ticket_models import TicketSummary


class TicketSummaryBuilder:
    def build_summary(self, context) -> TicketSummary:
        evidence = (context.evidence or "").strip()
        attachment_count = len(context.attachments or [])
        if attachment_count:
            attachment_text = (
                f"{attachment_count} anexo recebido."
                if attachment_count == 1
                else f"{attachment_count} anexos recebidos."
            )
            if evidence and evidence != "Não informado":
                evidence = f"{attachment_text} {evidence}"
            else:
                evidence = attachment_text
        elif not evidence:
            evidence = "Não informado"

        return TicketSummary(
            requester=f"{context.user.full_name} ({context.user.login})",
            channel=context.channel,
            category=context.selected_category_name or "",
            description=context.organized_description or "",
            impact=context.impact_label or "",
            severity=context.severity or "",
            location=context.location or "",
            evidence=evidence,
            suggested_title=context.suggested_title or "",
        )

    def render_summary_message(self, summary: TicketSummary) -> str:
        return (
            "🏁 **Revisão Final**\n\n"
            "Tudo pronto! Confira os dados antes de gerarmos o ticket:\n"
            "━━━━━━━━━━━━━━━━━━\n"
            f"📂 **Categoria:** {summary.category}\n"
            f"📝 **Resumo:** {summary.description}\n"
            f"🚦 **Impacto:** {summary.impact}\n"
            f"📍 **Local:** {summary.location}\n"
            f"📎 **Anexos:** {summary.evidence}\n"
            "━━━━━━━━━━━━━━━━━━\n\n"
            "Podemos abrir o chamado?\n\n"
            "1️⃣ **Sim, confirmar abertura**\n"
            "2️⃣ **Preciso corrigir algo**\n"
            "3️⃣ **Desistir e cancelar**"
        )
