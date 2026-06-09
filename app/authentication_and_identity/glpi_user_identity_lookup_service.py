from dataclasses import dataclass
import logging
from typing import Protocol

from app.glpi_integration_reserved.glpi_future_real_client import (
    GLPIClientError,
    GLPIRealClient,
)
from app.glpi_integration_reserved.glpi_search_options import (
    GLPISearchOption,
    GLPISearchOptionsResolver,
)


logger = logging.getLogger(__name__)

@dataclass(slots=True)
class GLPIUserIdentity:
    id: int
    name: str
    firstname: str
    realname: str
    email: str
    phone: str
    phone2: str
    mobile: str
    registration_number: str
    is_active: bool

class GLPIUserIdentityLookupServiceInterface(Protocol):
    def find_active_candidates_by_cpf_prefix(
        self, cpf_prefix: str
    ) -> list[GLPIUserIdentity]:
        ...


class GLPIRealUserIdentityLookupService(GLPIUserIdentityLookupServiceInterface):
    def __init__(self, client: GLPIRealClient) -> None:
        self.client = client
        self._resolver: GLPISearchOptionsResolver | None = None

    def find_active_candidates_by_cpf_prefix(
        self, cpf_prefix: str
    ) -> list[GLPIUserIdentity]:
        from app.authentication_and_identity.channel_identifier_normalizer import (
            ChannelIdentifierNormalizer,
        )
        from app.authentication_and_identity.document_partial_validator import (
            DocumentPartialValidator,
        )

        try:
            resolver = self._get_resolver()
            field_set = self._resolve_user_fields(resolver)
        except (GLPIClientError, ValueError):
            logger.exception("glpi_user_search_options_unavailable")
            return []

        registration_option = field_set["registration_number"]
        if not isinstance(registration_option, GLPISearchOption):
            return []

        rows_by_user_id: dict[int, dict] = {}
        for term in self._cpf_search_terms(cpf_prefix):
            try:
                    response = self.client.search(
                        "User",
                        self._build_user_search_params(
                            registration_option,
                        term,
                        field_set["forced_display_ids"],
                    ),
                )
            except GLPIClientError:
                logger.exception("glpi_user_cpf_search_failed")
                continue
            for row in response.get("data", []):
                if not isinstance(row, dict):
                    continue
                user_id = self._row_int(row, field_set["id"])
                if user_id:
                    rows_by_user_id[user_id] = row

        validator = DocumentPartialValidator(pepper="", prefix_length=len(cpf_prefix))
        candidates: list[GLPIUserIdentity] = []
        for row in rows_by_user_id.values():
            identity = self._identity_from_row(row, field_set)
            if identity is None or not identity.is_active:
                continue
            full_cpf = ChannelIdentifierNormalizer.normalize_cpf(
                identity.registration_number
            )
            if validator.compare_partial_with_full(cpf_prefix, full_cpf):
                candidates.append(identity)

        logger.info(
            "glpi_user_cpf_lookup_completed",
            extra={"candidates_count": len(candidates)},
        )
        return candidates

    def _get_resolver(self) -> GLPISearchOptionsResolver:
        if self._resolver is None:
            self._resolver = GLPISearchOptionsResolver(
                self.client.list_search_options("User")
            )
        return self._resolver

    def _resolve_user_fields(
        self,
        resolver: GLPISearchOptionsResolver,
    ) -> dict[str, object]:
        phone_fields = resolver.find_many(
            fields=("phone", "phone2", "mobile"),
            names=(
                "Phone",
                "Phone 2",
                "Mobile phone",
                "Celular",
                "Telefone",
                "Telefone 2",
            ),
        )
        registration_number = resolver.require_one(
            fields=("registration_number", "cpf"),
            names=(
                "Administrative number",
                "Registration number",
                "Matricula",
                "Matrícula",
                "CPF",
                "Documento",
            ),
        )
        fields: dict[str, object] = {
            "id": resolver.require_one(fields=("id",), names=("ID",)),
            "name": resolver.require_one(fields=("name",), names=("Login", "Name")),
            "firstname": resolver.find_one(fields=("firstname",), names=("First name", "Nome")),
            "realname": resolver.find_one(fields=("realname",), names=("Surname", "Sobrenome")),
            "email": resolver.find_one(fields=("email",), names=("Email", "E-mail")),
            "registration_number": registration_number,
            "is_active": resolver.find_one(fields=("is_active",), names=("Active", "Ativo")),
            "phone_fields": phone_fields,
        }
        forced_ids = [
            option.id
            for option in fields.values()
            if isinstance(option, GLPISearchOption)
        ]
        forced_ids.extend(option.id for option in phone_fields)
        fields["forced_display_ids"] = list(dict.fromkeys(forced_ids))
        return fields

    @staticmethod
    def _build_user_search_params(
        search_option: GLPISearchOption,
        search_value: str,
        forced_display_ids: list[int],
    ) -> dict[str, str | int]:
        params: dict[str, str | int] = {
            "criteria[0][field]": search_option.id,
            "criteria[0][searchtype]": "contains",
            "criteria[0][value]": search_value,
            "range": "0-49",
        }
        for index, field_id in enumerate(forced_display_ids):
            params[f"forcedisplay[{index}]"] = field_id
        return params

    @staticmethod
    def _cpf_search_terms(cpf_prefix: str) -> list[str]:
        clean_prefix = "".join(ch for ch in str(cpf_prefix) if ch.isdigit())
        terms = [clean_prefix]
        if len(clean_prefix) >= 3:
            terms.append(clean_prefix[:3])
        if len(clean_prefix) >= 2:
            terms.append(clean_prefix[:2])
        return list(dict.fromkeys(term for term in terms if term))

    def _identity_from_row(
        self,
        row: dict,
        field_set: dict[str, object],
    ) -> GLPIUserIdentity | None:
        user_id = self._row_int(row, field_set["id"])
        if not user_id:
            return None
        phone_fields: list[GLPISearchOption] = field_set["phone_fields"]  # type: ignore[assignment]
        phone_values = [self._row_str(row, option) for option in phone_fields]
        return GLPIUserIdentity(
            id=user_id,
            name=self._row_str(row, field_set["name"]),
            firstname=self._row_str(row, field_set.get("firstname")),
            realname=self._row_str(row, field_set.get("realname")),
            email=self._row_str(row, field_set.get("email")),
            phone=phone_values[0] if len(phone_values) > 0 else "",
            phone2=phone_values[1] if len(phone_values) > 1 else "",
            mobile=phone_values[2] if len(phone_values) > 2 else "",
            registration_number=self._row_str(row, field_set["registration_number"]),
            is_active=self._row_bool(row, field_set.get("is_active"), default=True),
        )

    @classmethod
    def _row_int(cls, row: dict, option: object) -> int:
        try:
            return int(cls._row_str(row, option))
        except (TypeError, ValueError):
            return 0

    @classmethod
    def _row_bool(cls, row: dict, option: object, *, default: bool) -> bool:
        if option is None:
            return default
        value = cls._row_str(row, option).strip().casefold()
        if value == "":
            return default
        return value not in {"0", "false", "no", "nao", "não", "inactive", "inativo"}

    @classmethod
    def _row_str(cls, row: dict, option: object) -> str:
        if not isinstance(option, GLPISearchOption):
            return ""
        value = cls._first_present(
            row,
            (str(option.id), option.id, option.field, option.name),
        )
        if isinstance(value, dict):
            value = value.get("value") or value.get("name") or value.get("displayname")
        return "" if value is None else str(value)

    @staticmethod
    def _first_present(row: dict, keys: tuple[object, ...]) -> object | None:
        for key in keys:
            if key in row:
                return row[key]
        return None


class MockGLPIUserIdentityLookupService(GLPIUserIdentityLookupServiceInterface):
    """
    Mock implementation for local testing.
    """
    def __init__(self):
        self.mock_users = [
            GLPIUserIdentity(
                id=266,
                name="pedro.torres",
                firstname="Pedro",
                realname="Pedro Américo Paletot de Alcântara Torres",
                email="pedro.torres@terrapremium.com.br",
                phone="",
                phone2="",
                mobile="66999990980",
                registration_number="099.150.671-51",
                is_active=True
            ),
            GLPIUserIdentity(
                id=300,
                name="joao.silva",
                firstname="Joao",
                realname="Joao da Silva",
                email="joao.silva@empresa.local",
                phone="66988887777",
                phone2="",
                mobile="",
                registration_number="12345678901",
                is_active=True
            ),
            # Duplicated phone for ambiguity test
            GLPIUserIdentity(
                id=301,
                name="maria.souza",
                firstname="Maria",
                realname="Maria Souza",
                email="maria.souza@empresa.local",
                phone="66988887777",
                phone2="",
                mobile="",
                registration_number="12345699999",
                is_active=True
            )
        ]

    def find_active_candidates_by_cpf_prefix(
        self, cpf_prefix: str
    ) -> list[GLPIUserIdentity]:
        from app.authentication_and_identity.channel_identifier_normalizer import ChannelIdentifierNormalizer
        from app.authentication_and_identity.document_partial_validator import DocumentPartialValidator

        candidates = []
        validator = DocumentPartialValidator(pepper="", prefix_length=len(cpf_prefix))

        for u in self.mock_users:
            if not u.is_active:
                continue
            full_cpf = ChannelIdentifierNormalizer.normalize_cpf(u.registration_number)
            if validator.compare_partial_with_full(cpf_prefix, full_cpf):
                candidates.append(u)

        return candidates
