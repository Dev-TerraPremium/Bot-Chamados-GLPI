from dataclasses import asdict, dataclass
import json
import time
import unicodedata
from typing import Any, Protocol

from app.application_config.settings import AppSettings
from app.distributed_runtime.redis_connection import get_redis_client
from app.glpi_integration_reserved.glpi_future_real_client import (
    GLPIClientError,
    GLPIRealClient,
)
from app.glpi_integration_reserved.glpi_integration_config import GLPIIntegrationConfig
from app.glpi_integration_reserved.glpi_search_options import (
    GLPISearchOption,
    GLPISearchOptionsResolver,
)


@dataclass(frozen=True, slots=True)
class GLPILocationOption:
    id: int
    name: str
    complete_name: str
    entity_id: int
    parent_id: int = 0
    level: int = 0

    @property
    def display_name(self) -> str:
        return self.complete_name or self.name


class GLPILocationCatalogServiceInterface(Protocol):
    def get_locations(self) -> list[GLPILocationOption]:
        ...

    def get_by_id(self, location_id: int) -> GLPILocationOption | None:
        ...

    def search(self, query: str, *, limit: int = 5) -> list[GLPILocationOption]:
        ...

    def get_user_default_location(self, user_id: int) -> GLPILocationOption | None:
        ...


class StaticGLPILocationCatalogService(GLPILocationCatalogServiceInterface):
    def __init__(self) -> None:
        self.locations = [
            GLPILocationOption(1, "Matriz", "Matriz", 3),
            GLPILocationOption(91, "Rondonópolis", "Rondonópolis", 3),
            GLPILocationOption(92, "Filial 92", "Filial 92", 3),
            GLPILocationOption(93, "Filial 93", "Filial 93", 3),
        ]

    def get_locations(self) -> list[GLPILocationOption]:
        return self.locations.copy()

    def get_by_id(self, location_id: int) -> GLPILocationOption | None:
        return next((item for item in self.locations if item.id == location_id), None)

    def search(self, query: str, *, limit: int = 5) -> list[GLPILocationOption]:
        return _search_locations(self.locations, query, limit=limit)

    def get_user_default_location(self, user_id: int) -> GLPILocationOption | None:
        return None


class RealGLPILocationCatalogService(GLPILocationCatalogServiceInterface):
    CACHE_KEY = "bot:glpi:location_catalog:v1"

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
        self._memory_cache: tuple[float, list[GLPILocationOption]] | None = None

    def get_locations(self) -> list[GLPILocationOption]:
        return self._load_locations()

    def get_by_id(self, location_id: int) -> GLPILocationOption | None:
        return next(
            (location for location in self._load_locations() if location.id == location_id),
            None,
        )

    def search(self, query: str, *, limit: int = 5) -> list[GLPILocationOption]:
        return _search_locations(self._load_locations(), query, limit=limit)

    def get_user_default_location(self, user_id: int) -> GLPILocationOption | None:
        try:
            user_payload = self.client.get_item("User", user_id)
        except GLPIClientError:
            return None
        location_id = int(user_payload.get("locations_id") or 0)
        if not location_id:
            return None
        return self.get_by_id(location_id)

    def _load_locations(self) -> list[GLPILocationOption]:
        cached = self._load_from_cache()
        if cached is not None:
            return cached

        resolver = GLPISearchOptionsResolver(self.client.list_search_options("Location"))
        fields = self._resolve_location_fields(resolver)
        params = self._build_location_search_params(fields["forced_display_ids"])
        response = self.client.search("Location", params)
        locations = [
            location
            for row in response.get("data", [])
            if isinstance(row, dict)
            for location in [self._location_from_row(row, fields)]
            if location is not None and location.entity_id in {0, self.entity_id}
        ]
        locations.sort(key=lambda item: (item.display_name.casefold(), item.id))
        self._save_to_cache(locations)
        return locations

    def _load_from_cache(self) -> list[GLPILocationOption] | None:
        if self.redis_client is not None:
            raw_value = self.redis_client.get(self.CACHE_KEY)
            if raw_value:
                return self._decode_locations(raw_value)
        if self._memory_cache is None:
            return None
        expires_at, locations = self._memory_cache
        if expires_at < time.time():
            self._memory_cache = None
            return None
        return locations

    def _save_to_cache(self, locations: list[GLPILocationOption]) -> None:
        payload = json.dumps([asdict(location) for location in locations], ensure_ascii=False)
        if self.redis_client is not None:
            self.redis_client.setex(self.CACHE_KEY, self.cache_ttl_seconds, payload)
        self._memory_cache = (time.time() + self.cache_ttl_seconds, locations)

    @staticmethod
    def _decode_locations(raw_value: bytes | str) -> list[GLPILocationOption]:
        if isinstance(raw_value, bytes):
            raw_value = raw_value.decode("utf-8")
        return [GLPILocationOption(**item) for item in json.loads(raw_value)]

    @staticmethod
    def _resolve_location_fields(
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
                fields=("locations_id",),
                names=("Father", "Parent location", "Localidade pai"),
            ),
            "level": resolver.find_one(fields=("level",), names=("Level", "Nivel")),
        }
        forced_ids = [
            option.id
            for option in fields.values()
            if isinstance(option, GLPISearchOption)
        ]
        fields["forced_display_ids"] = list(dict.fromkeys(forced_ids))
        return fields

    @staticmethod
    def _build_location_search_params(
        forced_display_ids: list[int],
    ) -> dict[str, str | int]:
        params: dict[str, str | int] = {"range": "0-999"}
        for index, field_id in enumerate(forced_display_ids):
            params[f"forcedisplay[{index}]"] = field_id
        return params

    def _location_from_row(
        self,
        row: dict,
        fields: dict[str, object],
    ) -> GLPILocationOption | None:
        location_id = _row_int(row, fields["id"])
        if not location_id:
            return None
        name = _row_str(row, fields["name"])
        complete_name = _row_str(row, fields.get("complete_name")) or name
        entity_id = _row_int(row, fields["entity_id"])
        if not entity_id and _row_str(row, fields["entity_id"]):
            entity_id = self.entity_id
        return GLPILocationOption(
            id=location_id,
            name=name,
            complete_name=complete_name,
            entity_id=entity_id,
            parent_id=_row_int(row, fields.get("parent_id")),
            level=_row_int(row, fields.get("level")),
        )


def build_location_catalog_service(
    settings: AppSettings,
) -> GLPILocationCatalogServiceInterface:
    if not settings.is_glpi_real_mode:
        return StaticGLPILocationCatalogService()

    redis_client = None
    if settings.is_redis_state_enabled:
        redis_client = get_redis_client(settings.redis_url)
    return RealGLPILocationCatalogService(
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


def _search_locations(
    locations: list[GLPILocationOption],
    query: str,
    *,
    limit: int,
) -> list[GLPILocationOption]:
    normalized_query = _normalize(query)
    tokens = [token for token in normalized_query.split() if len(token) > 1]
    if not tokens:
        return []

    scored: list[tuple[int, GLPILocationOption]] = []
    for location in locations:
        haystack = _normalize(f"{location.name} {location.complete_name}")
        compact_haystack = haystack.replace(" ", "")
        if not all(token in haystack or token in compact_haystack for token in tokens):
            continue
        score = 10
        if _normalize(location.name) == normalized_query:
            score += 20
        if normalized_query in _normalize(location.complete_name):
            score += 10
        score += min(location.level, 5)
        scored.append((score, location))

    scored.sort(key=lambda item: (-item[0], item[1].display_name.casefold()))
    return [location for _, location in scored[:limit]]


def _row_int(row: dict, option: object) -> int:
    try:
        return int(_row_str(row, option))
    except (TypeError, ValueError):
        return 0


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
    return value.strip()
