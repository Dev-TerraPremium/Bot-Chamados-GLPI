import fakeredis
import httpx

from app.distributed_runtime.category_usage_tracker import RedisCategoryUsageTracker
from app.glpi_integration_reserved.glpi_category_catalog_service import (
    RealGLPICategoryCatalogService,
    StaticGLPICategoryCatalogService,
)
from app.glpi_integration_reserved.glpi_future_real_client import GLPIRealClient
from app.glpi_integration_reserved.glpi_integration_config import GLPIIntegrationConfig


def build_category_client() -> GLPIRealClient:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/initSession"):
            return httpx.Response(200, json={"session_token": "session"})
        if request.url.path.endswith("/changeActiveProfile") or request.url.path.endswith("/changeActiveEntities"):
            return httpx.Response(200, json={})
        if request.url.path.endswith("/listSearchOptions/ITILCategory"):
            return httpx.Response(
                200,
                json={
                    "2": {"name": "ID", "field": "id"},
                    "1": {"name": "Name", "field": "name"},
                    "80": {"name": "Complete name", "field": "completename"},
                    "3": {"name": "Entity", "field": "entities_id"},
                    "4": {"name": "Parent category", "field": "itilcategories_id"},
                    "5": {"name": "Level", "field": "level"},
                    "6": {"name": "Visible in Helpdesk", "field": "is_helpdeskvisible"},
                    "7": {"name": "Incident", "field": "is_incident"},
                    "8": {"name": "Request", "field": "is_request"},
                },
            )
        if request.url.path.endswith("/search/ITILCategory"):
            return httpx.Response(
                200,
                json={
                    "data": [
                        {
                            "2": 544,
                            "1": "WI-FI",
                            "80": "INFRAESTRUTURA > REDES > WI-FI",
                            "3": 3,
                            "4": 528,
                            "5": 3,
                            "6": 1,
                            "7": 1,
                            "8": 1,
                        },
                        {
                            "2": 455,
                            "1": "COMPUTADORES",
                            "80": "INFRAESTRUTURA > COMPUTADORES",
                            "3": 3,
                            "4": 408,
                            "5": 2,
                            "6": 1,
                            "7": 1,
                            "8": 1,
                        },
                        {
                            "2": 999,
                            "1": "Categoria de outra entidade",
                            "80": "OUTRA > Categoria",
                            "3": 1,
                            "6": 1,
                        },
                        {
                            "2": 998,
                            "1": "Categoria oculta",
                            "80": "TI > Oculta",
                            "3": 3,
                            "6": 0,
                        },
                    ]
                },
            )
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


def test_real_category_catalog_filters_entity_and_helpdesk_visibility() -> None:
    catalog = RealGLPICategoryCatalogService(build_category_client(), entity_id=3)

    categories = catalog.get_categories(ticket_type=1)

    assert [category.id for category in categories] == [455, 544]
    assert catalog.search("wifi", ticket_type=1)[0].id == 544


def test_redis_category_usage_tracker_uses_global_scores_then_seed_defaults() -> None:
    redis_client = fakeredis.FakeRedis()
    tracker = RedisCategoryUsageTracker(redis_client)
    catalog = StaticGLPICategoryCatalogService()

    tracker.increment(544)
    tracker.increment(544)
    tracker.increment(455)

    top_ids = [category.id for category in tracker.top_categories(catalog, limit=5)]

    assert top_ids[:2] == [544, 455]
    assert 490 in top_ids
