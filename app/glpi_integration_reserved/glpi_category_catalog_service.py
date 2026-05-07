from dataclasses import asdict, dataclass
import json
import time
import unicodedata
import re
from typing import Any, Protocol

from app.application_config.settings import AppSettings
from app.distributed_runtime.redis_connection import get_redis_client
from app.glpi_integration_reserved.glpi_category_mapping_service import (
    DEFAULT_GLPI_CATEGORY_IDS,
)
from app.glpi_integration_reserved.glpi_future_real_client import (
    GLPIClientError,
    GLPIRealClient,
)
from app.glpi_integration_reserved.glpi_integration_config import GLPIIntegrationConfig
from app.glpi_integration_reserved.glpi_search_options import (
    GLPISearchOption,
    GLPISearchOptionsResolver,
)
from app.triage_rules.category_catalog import CATEGORY_OPTIONS


DEFAULT_TOP_CATEGORY_IDS = (535, 455, 490, 416, 622)


@dataclass(frozen=True, slots=True)
class GLPICategoryOption:
    id: int
    name: str
    complete_name: str
    entity_id: int
    parent_id: int = 0
    level: int = 0
    is_helpdesk_visible: bool = True
    is_incident: bool = True
    is_request: bool = True

    @property
    def display_name(self) -> str:
        return self.complete_name or self.name


class GLPICategoryCatalogServiceInterface(Protocol):
    def get_categories(self, ticket_type: int | None = None) -> list[GLPICategoryOption]:
        ...

    def get_by_id(self, category_id: int) -> GLPICategoryOption | None:
        ...

    def search(
        self,
        query: str,
        *,
        ticket_type: int | None = None,
        limit: int = 5,
    ) -> list[GLPICategoryOption]:
        ...


class StaticGLPICategoryCatalogService(GLPICategoryCatalogServiceInterface):
    def __init__(self) -> None:
        self.categories = [
            GLPICategoryOption(
                id=DEFAULT_GLPI_CATEGORY_IDS[category.id],
                name=category.name,
                complete_name=category.name,
                entity_id=3,
                level=1,
            )
            for category in CATEGORY_OPTIONS
        ]

    def get_categories(self, ticket_type: int | None = None) -> list[GLPICategoryOption]:
        return self.categories.copy()

    def get_by_id(self, category_id: int) -> GLPICategoryOption | None:
        return next((item for item in self.categories if item.id == category_id), None)

    def search(
        self,
        query: str,
        *,
        ticket_type: int | None = None,
        limit: int = 5,
    ) -> list[GLPICategoryOption]:
        return _search_categories(self.get_categories(ticket_type), query, limit=limit)


class RealGLPICategoryCatalogService(GLPICategoryCatalogServiceInterface):
    CACHE_KEY = "bot:glpi:category_catalog:v2"

    def __init__(
        self,
        client: GLPIRealClient,
        *,
        entity_id: int,
        redis_client=None,
        cache_ttl_seconds: int = 600,
    ) -> None:
        self.client = client
        self.entity_id = entity_id
        self.redis_client = redis_client
        self.cache_ttl_seconds = cache_ttl_seconds
        self._memory_cache: tuple[float, list[GLPICategoryOption]] | None = None

    def get_categories(self, ticket_type: int | None = None) -> list[GLPICategoryOption]:
        categories = self._load_categories()
        return [
            category
            for category in categories
            if self._is_available_for_ticket_type(category, ticket_type)
        ]

    def get_by_id(self, category_id: int) -> GLPICategoryOption | None:
        return next(
            (category for category in self._load_categories() if category.id == category_id),
            None,
        )

    def search(
        self,
        query: str,
        *,
        ticket_type: int | None = None,
        limit: int = 5,
    ) -> list[GLPICategoryOption]:
        return _search_categories(
            self.get_categories(ticket_type),
            query,
            limit=limit,
        )

    def _load_categories(self) -> list[GLPICategoryOption]:
        cached = self._load_from_cache()
        if cached is not None:
            return cached

        resolver = GLPISearchOptionsResolver(
            self.client.list_search_options("ITILCategory")
        )
        fields = self._resolve_category_fields(resolver)
        params = self._build_category_search_params(fields["forced_display_ids"])
        response = self.client.search("ITILCategory", params)
        categories = [
            category
            for row in response.get("data", [])
            if isinstance(row, dict)
            for category in [self._category_from_row(row, fields)]
            if category is not None
            and category.entity_id == self.entity_id
            and category.is_helpdesk_visible
        ]
        categories.sort(key=lambda item: (item.complete_name.casefold(), item.id))
        self._save_to_cache(categories)
        return categories

    def _load_from_cache(self) -> list[GLPICategoryOption] | None:
        if self.redis_client is not None:
            raw_value = self.redis_client.get(self.CACHE_KEY)
            if raw_value:
                return self._decode_categories(raw_value)
        if self._memory_cache is None:
            return None
        expires_at, categories = self._memory_cache
        if expires_at < time.time():
            self._memory_cache = None
            return None
        return categories

    def _save_to_cache(self, categories: list[GLPICategoryOption]) -> None:
        payload = json.dumps([asdict(category) for category in categories], ensure_ascii=False)
        if self.redis_client is not None:
            self.redis_client.setex(self.CACHE_KEY, self.cache_ttl_seconds, payload)
        self._memory_cache = (time.time() + self.cache_ttl_seconds, categories)

    @staticmethod
    def _decode_categories(raw_value: bytes | str) -> list[GLPICategoryOption]:
        if isinstance(raw_value, bytes):
            raw_value = raw_value.decode("utf-8")
        return [GLPICategoryOption(**item) for item in json.loads(raw_value)]

    @staticmethod
    def _resolve_category_fields(
        resolver: GLPISearchOptionsResolver,
    ) -> dict[str, object]:
        fields: dict[str, object] = {
            "id": resolver.require_one(fields=("id",), names=("ID",)),
            "name": resolver.require_one(fields=("name",), names=("Name", "Nome")),
            "complete_name": resolver.find_one(
                fields=("completename",),
                names=("Complete name", "Nome completo"),
            ),
            "entity_id": resolver.require_one(
                fields=("entities_id",),
                names=("Entity", "Entidade"),
            ),
            "parent_id": resolver.find_one(
                fields=("itilcategories_id",),
                names=("Father", "Parent category", "Categoria pai"),
            ),
            "level": resolver.find_one(fields=("level",), names=("Level", "Nivel")),
            "is_helpdesk_visible": resolver.find_one(
                fields=("is_helpdeskvisible",),
                names=("Visible in Helpdesk", "Visible", "Visivel"),
            ),
            "is_incident": resolver.find_one(fields=("is_incident",), names=("Incident",)),
            "is_request": resolver.find_one(fields=("is_request",), names=("Request",)),
        }
        forced_ids = [
            option.id
            for option in fields.values()
            if isinstance(option, GLPISearchOption)
        ]
        fields["forced_display_ids"] = list(dict.fromkeys(forced_ids))
        return fields

    @staticmethod
    def _build_category_search_params(
        forced_display_ids: list[int],
    ) -> dict[str, str | int]:
        params: dict[str, str | int] = {"range": "0-999"}
        for index, field_id in enumerate(forced_display_ids):
            params[f"forcedisplay[{index}]"] = field_id
        return params

    def _category_from_row(
        self,
        row: dict,
        fields: dict[str, object],
    ) -> GLPICategoryOption | None:
        category_id = _row_int(row, fields["id"])
        if not category_id:
            return None
        name = _row_str(row, fields["name"])
        complete_name = _row_str(row, fields.get("complete_name")) or name
        entity_id = _row_int(row, fields["entity_id"])
        if not entity_id and _row_str(row, fields["entity_id"]):
            entity_id = self.entity_id

        return GLPICategoryOption(
            id=category_id,
            name=name,
            complete_name=complete_name,
            entity_id=entity_id,
            parent_id=_row_int(row, fields.get("parent_id")),
            level=_row_int(row, fields.get("level")),
            is_helpdesk_visible=_row_bool(
                row,
                fields.get("is_helpdesk_visible"),
                default=True,
            ),
            is_incident=_row_bool(row, fields.get("is_incident"), default=True),
            is_request=_row_bool(row, fields.get("is_request"), default=True),
        )

    @staticmethod
    def _is_available_for_ticket_type(
        category: GLPICategoryOption,
        ticket_type: int | None,
    ) -> bool:
        if ticket_type == 1:
            return category.is_incident
        if ticket_type == 2:
            return category.is_request
        return True


def build_category_catalog_service(
    settings: AppSettings,
) -> GLPICategoryCatalogServiceInterface:
    if not settings.is_glpi_real_mode:
        return StaticGLPICategoryCatalogService()

    redis_client = None
    if settings.is_redis_state_enabled:
        redis_client = get_redis_client(settings.redis_url)
    return RealGLPICategoryCatalogService(
        GLPIRealClient(
            GLPIIntegrationConfig(
                base_url=settings.glpi_base_url,
                app_token=settings.glpi_app_token,
                user_token=settings.glpi_user_token,
                integration_mode=settings.glpi_integration_mode,
                default_entity_id=settings.glpi_default_entity_id,
                default_profile_id=settings.glpi_default_profile_id,
                default_requester_user_id=settings.glpi_default_requester_user_id,
                allow_insecure_http=settings.glpi_allow_insecure_http,
                http_timeout_seconds=settings.glpi_http_timeout_seconds,
                ticket_requester_search_field=settings.glpi_ticket_requester_search_field,
            )
        ),
        entity_id=settings.glpi_default_entity_id,
        redis_client=redis_client,
    )


def _search_categories(
    categories: list[GLPICategoryOption],
    query: str,
    *,
    limit: int,
) -> list[GLPICategoryOption]:
    normalized_query = _normalize(query)
    tokens = [token for token in normalized_query.split() if len(token) > 1]
    if not tokens:
        return []
    scored: list[tuple[int, GLPICategoryOption]] = []
    for category in categories:
        haystack = _normalize(f"{category.name} {category.complete_name}")
        compact_haystack = haystack.replace(" ", "")
        if not all(token in haystack or token in compact_haystack for token in tokens):
            continue
        score = 10
        if _normalize(category.name) == normalized_query:
            score += 20
        if normalized_query in _normalize(category.complete_name):
            score += 10
        score += min(category.level, 5)
        scored.append((score, category))
    scored.sort(key=lambda item: (-item[0], item[1].complete_name.casefold()))
    return [category for _, category in scored[:limit]]


def _row_int(row: dict, option: object) -> int:
    try:
        return int(_row_str(row, option))
    except (TypeError, ValueError):
        return 0


def _row_bool(row: dict, option: object, *, default: bool) -> bool:
    if option is None:
        return default
    value = _row_str(row, option).strip().casefold()
    if value == "":
        return default
    return value not in {"0", "false", "no", "nao", "não", "inactive", "inativo"}


def _row_str(row: dict, option: object) -> str:
    if not isinstance(option, GLPISearchOption):
        return ""
    value = _first_present(row, (str(option.id), option.id, option.field, option.name))
    if isinstance(value, dict):
        value = value.get("value") or value.get("name") or value.get("displayname")
    return "" if value is None else str(value)


def _first_present(row: dict, keys: tuple[object, ...]) -> object | None:
    for key in keys:
        if key in row:
            return row[key]
    return None


def _normalize(value: str) -> str:
    value = unicodedata.normalize("NFKD", value.casefold())
    value = "".join(char for char in value if not unicodedata.combining(char))
    value = re.sub(r"[^\w\s]", " ", value)
    return re.sub(r"\s+", " ", value).strip()
