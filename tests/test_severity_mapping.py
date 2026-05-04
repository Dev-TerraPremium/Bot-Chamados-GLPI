from app.triage_rules.severity_mapping_service import SeverityMappingService


def test_severity_mapping() -> None:
    service = SeverityMappingService()

    assert service.map_impact_to_severity(1) == "Baixa"
    assert service.map_impact_to_severity(2) == "Media"
    assert service.map_impact_to_severity(3) == "Alta"
    assert service.map_impact_to_severity(4) == "Alta"
    assert service.map_impact_to_severity(5) == "Critica"

