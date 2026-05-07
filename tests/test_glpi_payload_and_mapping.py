from app.glpi_integration_reserved.glpi_category_mapping_service import (
    GLPICategoryMappingService,
)
from app.glpi_integration_reserved.glpi_ticket_payload_builder import (
    GLPITicketPayloadBuilder,
)
from app.ticket_domain.ticket_models import TicketDraft


def test_glpi_category_mapping_uses_real_default_ids() -> None:
    mapping = GLPICategoryMappingService().map_internal_category_to_glpi(11)

    assert mapping.internal_category_name == "Ubiquiti / Wi-Fi"
    assert mapping.glpi_category_id == 544


def test_glpi_ticket_payload_builder_creates_rest_payload() -> None:
    draft = TicketDraft(
        requester_name="Pedro Torres",
        requester_login="pedro.torres",
        requester_email="pedro.torres@empresa.local",
        glpi_user_id=266,
        channel="web_simulator",
        opening_mode="Abertura assistida",
        category_id=2,
        category_name="Computador / Notebook",
        description="Estou com problema grave no meu desktop.",
        impact_id=3,
        impact_label="Afeta somente você e está parado",
        severity="Alta",
        location="TI - Matriz",
        evidence="Não informado",
        title="Computador / Notebook - Estou com problema grave no meu desktop",
    )

    payload = GLPITicketPayloadBuilder(
        default_entity_id=3,
        default_requester_user_id=266,
    ).build_from_ticket_draft(draft)

    assert payload["glpi_input"]["entities_id"] == 3
    assert payload["glpi_input"]["itilcategories_id"] == 455
    assert payload["glpi_input"]["_users_id_requester"] == 266
    assert payload["glpi_input"]["priority"] == 4
    assert "Descrição organizada" in payload["glpi_input"]["content"]


def test_glpi_ticket_payload_builder_uses_real_category_and_authenticated_requester() -> None:
    draft = TicketDraft(
        requester_name="Pedro Torres",
        requester_login="pedro.torres",
        requester_email="pedro.torres@terrapremium.com.br",
        glpi_user_id=266,
        channel="whatsapp",
        opening_mode="Abertura assistida",
        category_id=544,
        category_name="INFRAESTRUTURA > REDES > WI-FI",
        glpi_category_id=544,
        glpi_category_complete_name="INFRAESTRUTURA > REDES > WI-FI",
        description="Wi-Fi caindo no depósito.",
        impact_id=2,
        impact_label="Afeta somente a mim",
        severity="Média",
        location="TI",
        evidence="Não informado",
        title="Wi-Fi caindo",
    )

    payload = GLPITicketPayloadBuilder(
        default_entity_id=3,
        default_requester_user_id=999,
    ).build_from_ticket_draft(draft)

    assert payload["glpi_input"]["itilcategories_id"] == 544
    assert payload["glpi_input"]["_users_id_requester"] == 266
    assert payload["category_name"] == "INFRAESTRUTURA > REDES > WI-FI"
