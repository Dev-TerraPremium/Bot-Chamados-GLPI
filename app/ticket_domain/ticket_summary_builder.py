from app.ticket_domain.ticket_models import TicketSummary


class TicketSummaryBuilder:
    def build_summary(self, context) -> TicketSummary:
        return TicketSummary(
            requester=f"{context.user.full_name} ({context.user.login})",
            channel=context.channel,
            category=context.selected_category_name or "",
            description=context.organized_description or "",
            impact=context.impact_label or "",
            severity=context.severity or "",
            location=context.location or "",
            evidence=context.evidence or "Não informado",
            suggested_title=context.suggested_title or "",
        )

    def render_summary_message(self, summary: TicketSummary) -> str:
        return (
            "📋 **Confirme os dados do chamado:**\n\n"
            f"👤 **Solicitante:** {summary.requester}\n"
            f"💬 **Canal:** {summary.channel}\n"
            f"📚 **Categoria:** {summary.category}\n"
            f"📝 **Descrição:** {summary.description}\n"
            f"📊 **Impacto:** {summary.impact}\n"
            f"🚦 **Gravidade:** {summary.severity}\n"
            f"📍 **Localidade/Setor:** {summary.location}\n"
            f"📎 **Evidência:** {summary.evidence}\n"
            f"🏷️ **Título sugerido:** {summary.suggested_title}\n\n"
            "Deseja abrir o chamado?\n\n"
            "1. ✅ **Sim, abrir chamado**\n"
            "2. ✏️ **Corrigir informações**\n"
            "3. ❌ **Cancelar**"
        )
