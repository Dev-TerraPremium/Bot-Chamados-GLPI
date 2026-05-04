from app.ticket_domain.ticket_enums import TicketSeverity


class SeverityMappingService:
    IMPACT_TO_SEVERITY = {
        1: TicketSeverity.LOW.value,
        2: TicketSeverity.MEDIUM.value,
        3: TicketSeverity.HIGH.value,
        4: TicketSeverity.HIGH.value,
        5: TicketSeverity.CRITICAL.value,
    }

    def map_impact_to_severity(self, impact_id: int) -> str:
        if impact_id not in self.IMPACT_TO_SEVERITY:
            raise ValueError("Impacto invalido para mapeamento de gravidade.")
        return self.IMPACT_TO_SEVERITY[impact_id]

