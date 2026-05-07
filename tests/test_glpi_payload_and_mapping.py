import pytest

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
        impact_label="Afeta somente voce e esta parado",
        severity="Alta",
        location="TI - Matriz",
        evidence="Nao informado",
        title="Estou com problema grave no meu desktop",
    )

    payload = GLPITicketPayloadBuilder(
        default_entity_id=3,
        default_requester_user_id=266,
    ).build_from_ticket_draft(draft)

    content = payload["glpi_input"]["content"]
    assert payload["glpi_input"]["entities_id"] == 3
    assert payload["glpi_input"]["itilcategories_id"] == 455
    assert payload["glpi_input"]["_users_id_requester"] == 266
    assert payload["glpi_input"]["priority"] == 4
    assert "Estou com problema grave no meu desktop." in content
    assert "Localidade/Setor: TI - Matriz" in content
    assert "Gravidade calculada" not in content
    assert "Canal de origem" not in content
    assert "pedro.torres" not in content


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
        description="Wi-Fi caindo no deposito.",
        impact_id=2,
        impact_label="Afeta somente a mim",
        severity="Media",
        location="TI",
        evidence="Nao informado",
        title="Wi-Fi caindo",
    )

    payload = GLPITicketPayloadBuilder(
        default_entity_id=3,
        default_requester_user_id=999,
    ).build_from_ticket_draft(draft)

    assert payload["glpi_input"]["itilcategories_id"] == 544
    assert payload["glpi_input"]["_users_id_requester"] == 266
    assert payload["category_name"] == "INFRAESTRUTURA > REDES > WI-FI"


def test_glpi_ticket_payload_builder_keeps_glpi_content_free_of_internal_metadata() -> None:
    draft = TicketDraft(
        requester_name="Pedro Torres (Simulador)",
        requester_login="pedro.torres",
        requester_email="pedro.torres@terrapremium.com.br",
        glpi_user_id=266,
        channel="web_simulator",
        opening_mode="Abertura assistida",
        category_id=490,
        category_name="INFRAESTRUTURA > PERIFERICOS > MOUSE/TECLADO",
        glpi_category_id=490,
        glpi_category_complete_name="INFRAESTRUTURA > PERIFERICOS > MOUSE/TECLADO",
        description=(
            "Usuario informa que o mouse esta apresentando falha no clique, "
            "mesmo apos teste em outra entrada USB."
        ),
        impact_id=2,
        impact_label="Afeta somente voce, mas ainda consegue trabalhar",
        severity="Media",
        location="TI - Rondonopolis",
        evidence="Nao informado",
        title="Mouse com falha no clique",
    )

    payload = GLPITicketPayloadBuilder(
        default_entity_id=3,
        require_glpi_category=True,
    ).build_from_ticket_draft(draft)

    content = payload["glpi_input"]["content"]
    assert payload["glpi_input"]["name"] == "Mouse com falha no clique"
    assert "INFRAESTRUTURA" not in payload["glpi_input"]["name"]
    assert "Gravidade calculada" not in content
    assert "Canal de origem" not in content
    assert "web_simulator" not in content
    assert "Simulador" not in content
    assert "Pedro Torres" not in content
    assert "pedro.torres" not in content
    assert "INFRAESTRUTURA" not in content


def test_glpi_ticket_payload_builder_requires_real_category_in_real_mode() -> None:
    draft = TicketDraft(
        requester_name="Pedro Torres",
        requester_login="pedro.torres",
        requester_email="pedro.torres@terrapremium.com.br",
        glpi_user_id=266,
        channel="whatsapp",
        opening_mode="Abertura assistida",
        category_id=12,
        category_name="Outro",
        description="Teste controlado.",
        impact_id=1,
        impact_label="Duvida simples",
        severity="Baixa",
        location="TI",
        evidence="Nao informado",
        title="Teste controlado",
    )

    with pytest.raises(ValueError, match="Categoria GLPI real obrigatoria"):
        GLPITicketPayloadBuilder(
            default_entity_id=3,
            require_glpi_category=True,
        ).build_from_ticket_draft(draft)
