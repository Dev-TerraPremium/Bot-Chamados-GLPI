from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class GLPISearchOption:
    id: int
    name: str
    field: str
    table: str


class GLPISearchOptionsResolver:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.options = self._parse_options(payload)

    def require_one(
        self,
        *,
        fields: tuple[str, ...] = (),
        names: tuple[str, ...] = (),
    ) -> GLPISearchOption:
        option = self.find_one(fields=fields, names=names)
        if option is None:
            expected = ", ".join(fields or names)
            raise ValueError(f"Campo GLPI nao encontrado em listSearchOptions: {expected}")
        return option

    def find_one(
        self,
        *,
        fields: tuple[str, ...] = (),
        names: tuple[str, ...] = (),
    ) -> GLPISearchOption | None:
        matches = self.find_many(fields=fields, names=names)
        return matches[0] if matches else None

    def find_many(
        self,
        *,
        fields: tuple[str, ...] = (),
        names: tuple[str, ...] = (),
    ) -> list[GLPISearchOption]:
        normalized_fields = {self._normalize(value) for value in fields}
        normalized_names = {self._normalize(value) for value in names}
        matches: list[GLPISearchOption] = []
        for option in self.options:
            option_field = self._normalize(option.field)
            option_name = self._normalize(option.name)
            if option_field in normalized_fields or option_name in normalized_names:
                matches.append(option)
        return matches

    @staticmethod
    def _parse_options(payload: dict[str, Any]) -> list[GLPISearchOption]:
        options: list[GLPISearchOption] = []
        for raw_id, raw_option in payload.items():
            if not str(raw_id).isdigit() or not isinstance(raw_option, dict):
                continue
            options.append(
                GLPISearchOption(
                    id=int(raw_id),
                    name=str(raw_option.get("name") or ""),
                    field=str(raw_option.get("field") or ""),
                    table=str(raw_option.get("table") or ""),
                )
            )
        return options

    @staticmethod
    def _normalize(value: str) -> str:
        return value.strip().casefold().replace(" ", "_").replace("-", "_")
