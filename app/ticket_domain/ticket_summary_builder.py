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
        category = summary.category or "Sem categoria definida"
        description = summary.description or "Sem descrição informada"
        impact = summary.impact or "Impacto não informado"
        location = summary.location or "Localidade não informada"
        evidence = self._render_evidence_phrase(summary.evidence)
        return (
            "🏁 **Revisão Final**\n\n"
            f'Seu chamado será aberto na categoria **{category}**. '
            f'O resumo que será enviado é: "{description}". '
            f'O impacto informado é **{impact}**, na localidade **{location}**, '
            f"e {evidence}\n\n"
            "Posso abrir seu chamado agora?\n\n"
            "1️⃣ **Sim, confirmar abertura**\n"
            "2️⃣ **Preciso corrigir algo**\n"
            "3️⃣ **Desistir e cancelar**"
        )

    def _render_evidence_phrase(self, evidence: str) -> str:
        normalized = (evidence or "").strip()
        if not normalized or normalized == "Não informado":
            return "você não enviou anexos."
        if normalized == "Anexos enviados pelo WhatsApp.":
            return "você enviou anexos pelo WhatsApp."
        return f'as evidências registradas foram: "{normalized}".'
