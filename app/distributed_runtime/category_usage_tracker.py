from typing import Protocol

from app.application_config.settings import AppSettings
from app.distributed_runtime.redis_connection import get_redis_client
from app.glpi_integration_reserved.glpi_category_catalog_service import (
    DEFAULT_TOP_CATEGORY_IDS,
    GLPICategoryCatalogServiceInterface,
    GLPICategoryOption,
)


class CategoryUsageTrackerInterface(Protocol):
    def increment(self, category_id: int) -> None:
        ...

    def top_categories(
        self,
        catalog: GLPICategoryCatalogServiceInterface,
        *,
        ticket_type: int | None = None,
        limit: int = 5,
    ) -> list[GLPICategoryOption]:
        ...


class InMemoryCategoryUsageTracker(CategoryUsageTrackerInterface):
    def __init__(self) -> None:
        self.scores: dict[int, float] = {}

    def increment(self, category_id: int) -> None:
        self.scores[category_id] = self.scores.get(category_id, 0) + 1

    def top_categories(
        self,
        catalog: GLPICategoryCatalogServiceInterface,
        *,
        ticket_type: int | None = None,
        limit: int = 5,
    ) -> list[GLPICategoryOption]:
        return _resolve_top_categories(self.scores, catalog, ticket_type=ticket_type, limit=limit)


class RedisCategoryUsageTracker(CategoryUsageTrackerInterface):
    KEY = "bot:glpi:category_usage:v1"

    def __init__(self, redis_client) -> None:
        self.redis_client = redis_client

    def increment(self, category_id: int) -> None:
        self.redis_client.zincrby(self.KEY, 1, str(category_id))

    def top_categories(
        self,
        catalog: GLPICategoryCatalogServiceInterface,
        *,
        ticket_type: int | None = None,
        limit: int = 5,
    ) -> list[GLPICategoryOption]:
        raw_scores = self.redis_client.zrevrange(self.KEY, 0, limit - 1, withscores=True)
        scores: dict[int, float] = {}
        for raw_category_id, raw_score in raw_scores:
            if isinstance(raw_category_id, bytes):
                raw_category_id = raw_category_id.decode("utf-8")
            try:
                scores[int(raw_category_id)] = float(raw_score)
            except (TypeError, ValueError):
                continue
        return _resolve_top_categories(scores, catalog, ticket_type=ticket_type, limit=limit)


def build_category_usage_tracker(settings: AppSettings) -> CategoryUsageTrackerInterface:
    if settings.is_redis_state_enabled:
        return RedisCategoryUsageTracker(get_redis_client(settings.redis_url))
    return InMemoryCategoryUsageTracker()


def _resolve_top_categories(
    scores: dict[int, float],
    catalog: GLPICategoryCatalogServiceInterface,
    *,
    ticket_type: int | None,
    limit: int,
) -> list[GLPICategoryOption]:
    categories_by_id = {
        category.id: category for category in catalog.get_categories(ticket_type)
    }
    ordered_ids = [
        category_id
        for category_id, _ in sorted(
            scores.items(),
            key=lambda item: (-item[1], item[0]),
        )
        if category_id in categories_by_id
    ]
    for category_id in DEFAULT_TOP_CATEGORY_IDS:
        if category_id in categories_by_id and category_id not in ordered_ids:
            ordered_ids.append(category_id)
    return [categories_by_id[category_id] for category_id in ordered_ids[:limit]]
