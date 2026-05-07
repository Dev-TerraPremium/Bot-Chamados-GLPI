import httpx

from app.authentication_and_identity.glpi_user_identity_lookup_service import (
    GLPIRealUserIdentityLookupService,
)
from app.glpi_integration_reserved.glpi_future_real_client import GLPIRealClient
from app.glpi_integration_reserved.glpi_integration_config import GLPIIntegrationConfig


def build_client(rows: list[dict]) -> GLPIRealClient:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/initSession"):
            return httpx.Response(200, json={"session_token": "session"})
        if request.url.path.endswith("/changeActiveProfile") or request.url.path.endswith("/changeActiveEntities"):
            return httpx.Response(200, json={})
        if request.url.path.endswith("/listSearchOptions/User"):
            return httpx.Response(
                200,
                json={
                    "2": {"name": "ID", "field": "id"},
                    "1": {"name": "Login", "field": "name"},
                    "9": {"name": "First name", "field": "firstname"},
                    "34": {"name": "Surname", "field": "realname"},
                    "5": {"name": "Phone", "field": "phone"},
                    "6": {"name": "Phone 2", "field": "phone2"},
                    "7": {"name": "Mobile phone", "field": "mobile"},
                    "8": {"name": "Registration number", "field": "registration_number"},
                    "10": {"name": "Active", "field": "is_active"},
                    "11": {"name": "Email", "field": "email"},
                },
            )
        if request.url.path.endswith("/search/User"):
            value = request.url.params.get("criteria[0][value]", "")
            matched = [
                row
                for row in rows
                if value in str(row.get("5", ""))
                or value in str(row.get("6", ""))
                or value in str(row.get("7", ""))
            ]
            return httpx.Response(200, json={"data": matched})
        raise AssertionError(f"Unexpected request: {request.method} {request.url}")

    return GLPIRealClient(
        GLPIIntegrationConfig(
            base_url="https://glpi.local/apirest.php",
            app_token="app",
            user_token="user",
            default_entity_id=3,
            default_profile_id=4,
        ),
        transport=httpx.MockTransport(handler),
    )


def test_glpi_real_user_lookup_matches_phone_and_cpf_prefix() -> None:
    lookup = GLPIRealUserIdentityLookupService(
        build_client(
            [
                {
                    "2": 266,
                    "1": "pedro.torres",
                    "9": "Pedro",
                    "34": "Américo Paletot de Alcântara Torres",
                    "5": "66999990980",
                    "6": "",
                    "7": "",
                    "8": "099.150.671-51",
                    "10": 1,
                    "11": "pedro.torres@terrapremium.com.br",
                }
            ]
        )
    )

    candidates = lookup.find_active_candidates_by_channel_phone_and_cpf_prefix(
        "556699990980",
        "0991",
    )

    assert len(candidates) == 1
    assert candidates[0].id == 266
    assert candidates[0].name == "pedro.torres"


def test_glpi_real_user_lookup_returns_multiple_candidates_for_ambiguous_phone() -> None:
    lookup = GLPIRealUserIdentityLookupService(
        build_client(
            [
                {
                    "2": 300,
                    "1": "joao.silva",
                    "9": "Joao",
                    "34": "Silva",
                    "5": "66988887777",
                    "8": "1234",
                    "10": 1,
                },
                {
                    "2": 301,
                    "1": "maria.souza",
                    "9": "Maria",
                    "34": "Souza",
                    "5": "66988887777",
                    "8": "1239",
                    "10": 1,
                },
            ]
        )
    )

    candidates = lookup.find_active_candidates_by_channel_phone_and_cpf_prefix(
        "66988887777",
        "123",
    )

    assert {candidate.id for candidate in candidates} == {300, 301}
