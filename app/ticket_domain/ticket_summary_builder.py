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
            "Confira os dados antes de abrir o chamado:\n\n"
            f"📂 **Categoria:** {category}\n"
            f"📝 **Descrição:** {description}\n"
            f"🚦 **Impacto:** {impact}\n"
            f"📍 **Localidade:** {location}\n"
            f"📎 **Evidências:** {evidence}\n\n"
            "Se estiver tudo certo, confirme a abertura.\n"
            "Se precisar ajustar algo, escolha a opção de correção.\n\n"
            "Digite o número da opção desejada:\n"
            "1️⃣ **Sim, confirmar abertura**\n"
            "2️⃣ **Preciso corrigir algo**\n"
            "3️⃣ **Desistir e cancelar**"
        )

    def _render_evidence_phrase(self, evidence: str) -> str:
        normalized = (evidence or "").strip()
        if not normalized or normalized == "Não informado":
            return "Nenhuma evidência informada"
        if normalized == "Anexos enviados pelo WhatsApp.":
            return "Anexos enviados pelo WhatsApp"
        return normalized
