import logging
import base64
import json as jsonlib
from typing import Any

import httpx

from app.glpi_integration_reserved.glpi_client_interface import GLPIClientInterface
from app.glpi_integration_reserved.glpi_integration_config import GLPIIntegrationConfig
from app.shared_kernel.date_time_provider import DateTimeProvider
from app.ticket_domain.ticket_enums import TicketStatus
from app.ticket_domain.ticket_models import TicketCreated, TicketFollowup


logger = logging.getLogger(__name__)


class GLPIClientError(RuntimeError):
    """Raised when GLPI refuses or fails an operation."""


class GLPIRealClient(GLPIClientInterface):
    """GLPI REST API client used by production mode."""

    def __init__(
        self,
        config: GLPIIntegrationConfig,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.config = config
        self.base_url = config.normalized_base_url
        self._session_token: str | None = None
        self._transport = transport
        self._is_initializing_session = False

    def init_session(self) -> str:
        if self._session_token:
            return self._session_token

        response = self._request(
            "GET",
            "/initSession",
            headers={"Authorization": f"user_token {self.config.user_token}"},
            use_session=False,
        )
        session_token = response.get("session_token")
        if not session_token:
            raise GLPIClientError("GLPI nao retornou session_token.")
        self._session_token = str(session_token)
        self._is_initializing_session = True
        try:
            self._activate_profile_and_entity()
        except GLPIClientError:
            self._session_token = None
            raise
        finally:
            self._is_initializing_session = False
        return self._session_token

    def kill_session(self) -> None:
        if not self._session_token:
            return
        try:
            self._request("GET", "/killSession")
        finally:
            self._session_token = None

    def create_ticket(self, ticket_data: dict) -> TicketCreated:
        payload = {"input": ticket_data["glpi_input"]}
        response = self._request("POST", "/Ticket", json=payload)
        ticket_id = int(response.get("id") or response.get("item", {}).get("id") or 0)
        if not ticket_id:
            raise GLPIClientError("GLPI nao retornou ID do chamado criado.")
        attachments = ticket_data.get("attachments") or []
        attachment_errors = self._attach_documents(
            ticket_id,
            attachments,
        )
        if attachment_errors:
            self._create_attachment_failure_followup(ticket_id, attachment_errors)
        return self._created_ticket_from_payload(
            ticket_id,
            ticket_data,
            attachments_expected_count=len(attachments),
            attachments_uploaded_count=len(attachments) - len(attachment_errors),
            attachment_errors=attachment_errors,
        )

    def get_my_tickets(self, user_id: int) -> list[TicketCreated]:
        ticket_ids = self._search_ticket_ids_for_requester(user_id)
        tickets: list[TicketCreated] = []
        for ticket_id in ticket_ids[:5]:
            ticket = self.get_ticket_by_id(ticket_id, user_id)
            if ticket is not None:
                tickets.append(ticket)
        return tickets

    def get_ticket_by_id(self, ticket_id: int, user_id: int) -> TicketCreated | None:
        ticket_data = self._request("GET", f"/Ticket/{ticket_id}")
        if not self._ticket_belongs_to_user(ticket_id, ticket_data, user_id):
            return None
        return self._ticket_from_glpi(ticket_data, user_id)

    def add_followup(
        self, ticket_id: int, user_id: int, content: str
    ) -> TicketFollowup | None:
        ticket = self.get_ticket_by_id(ticket_id, user_id)
        if ticket is None:
            return None
        if ticket.status not in {TicketStatus.OPEN.value, TicketStatus.IN_PROGRESS.value}:
            return None

        payload = {
            "input": {
                "itemtype": "Ticket",
                "items_id": ticket_id,
                "users_id": user_id,
                "content": content,
                "is_private": 0,
            }
        }
        response = self._request("POST", "/ITILFollowup", json=payload)
        followup_id = int(response.get("id") or 0)
        return TicketFollowup(
            ticket_number=ticket_id,
            user_id=user_id,
            content=content,
            created_at=DateTimeProvider.utc_now_iso(),
        )

    def find_user_by_identifier(self, identifier: str) -> dict | None:
        response = self._request(
            "GET",
            "/search/User",
            params={
                "criteria[0][field]": 1,
                "criteria[0][searchtype]": "contains",
                "criteria[0][value]": identifier,
                "range": "0-1",
            },
        )
        rows = response.get("data", [])
        if not rows:
            return None
        row = rows[0]
        return {"raw": row, "identifier": identifier}

    def find_category_by_name(self, category_name: str) -> dict | None:
        response = self._request(
            "GET",
            "/search/ITILCategory",
            params={
                "criteria[0][field]": 1,
                "criteria[0][searchtype]": "contains",
                "criteria[0][value]": category_name,
                "range": "0-5",
            },
        )
        rows = response.get("data", [])
        if not rows:
            return None
        return {"raw": rows[0], "category_name": category_name}

    def list_search_options(self, itemtype: str) -> dict:
        return self._request("GET", f"/listSearchOptions/{itemtype}")

    def search(self, itemtype: str, params: dict[str, Any]) -> dict:
        return self._request("GET", f"/search/{itemtype}", params=params)

    def get_item(self, itemtype: str, item_id: int) -> dict:
        return self._request("GET", f"/{itemtype}/{item_id}")

    def get_ticket_related_items(self, ticket_id: int, itemtype: str) -> dict:
        return self._request("GET", f"/Ticket/{ticket_id}/{itemtype}")

    def healthcheck(self) -> dict:
        checks: dict[str, Any] = {
            "status": "ok",
            "base_url": self.base_url,
            "mode": self.config.integration_mode,
        }
        self.init_session()
        checks["session"] = "ok"
        checks["profile"] = (
            self.config.default_profile_id if self.config.default_profile_id else "default"
        )
        checks["entity"] = (
            self.config.default_entity_id if self.config.default_entity_id else "default"
        )
        self.list_search_options("User")
        checks["user_search_options"] = "ok"
        self.list_search_options("ITILCategory")
        checks["category_search_options"] = "ok"
        self.list_search_options("Ticket")
        checks["ticket_search_options"] = "ok"
        self.search("ITILCategory", {"range": "0-0"})
        checks["category_search"] = "ok"
        checks["ticket_create_permission"] = "not_mutated"
        return checks

    def _request(
        self,
        method: str,
        path: str,
        *,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
        use_session: bool = True,
        allow_session_retry: bool = True,
    ) -> dict:
        self._ensure_base_url_allowed()

        request_headers = {
            "App-Token": self.config.app_token,
            "Content-Type": "application/json",
        }
        session_token = self._session_token if use_session else None
        if use_session:
            request_headers["Session-Token"] = self.init_session()
        if headers:
            request_headers.update(headers)

        try:
            client_kwargs: dict[str, Any] = {
                "base_url": self.base_url,
                "timeout": self.config.http_timeout_seconds,
                "follow_redirects": False,
            }
            if self._transport is not None:
                client_kwargs["transport"] = self._transport
            with httpx.Client(
                **client_kwargs,
            ) as client:
                response = client.request(
                    method,
                    path,
                    headers=request_headers,
                    params=params,
                    json=json,
                )
                response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            if self._should_retry_after_unauthorized(
                exc,
                use_session=use_session,
                allow_session_retry=allow_session_retry,
                session_token=session_token,
            ):
                logger.info(
                    "glpi_session_retry_after_unauthorized",
                    extra={"method": method, "path": path},
                )
                self._session_token = None
                return self._request(
                    method,
                    path,
                    headers=headers,
                    params=params,
                    json=json,
                    use_session=use_session,
                    allow_session_retry=False,
                )
            safe_body = self._redact(str(exc.response.text))
            logger.warning(
                "glpi_http_status_error",
                extra={
                    "method": method,
                    "path": path,
                    "status_code": exc.response.status_code,
                    "body": safe_body,
                },
            )
            raise GLPIClientError("GLPI recusou a operacao solicitada.") from exc
        except httpx.HTTPError as exc:
            logger.warning(
                "glpi_http_error",
                extra={"method": method, "path": path, "error": str(exc)},
            )
            raise GLPIClientError("Nao foi possivel comunicar com o GLPI.") from exc

        if not response.content:
            return {}
        payload = response.json()
        if isinstance(payload, list):
            return {"items": payload}
        return payload

    def _request_multipart(
        self,
        method: str,
        path: str,
        *,
        files: dict[str, Any],
        allow_session_retry: bool = True,
    ) -> dict:
        self._ensure_base_url_allowed()
        session_token = self._session_token
        request_headers = {
            "App-Token": self.config.app_token,
            "Session-Token": self.init_session(),
        }
        try:
            client_kwargs: dict[str, Any] = {
                "base_url": self.base_url,
                "timeout": self.config.http_timeout_seconds,
                "follow_redirects": False,
            }
            if self._transport is not None:
                client_kwargs["transport"] = self._transport
            with httpx.Client(**client_kwargs) as client:
                response = client.request(
                    method,
                    path,
                    headers=request_headers,
                    files=files,
                )
                response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            if self._should_retry_after_unauthorized(
                exc,
                use_session=True,
                allow_session_retry=allow_session_retry,
                session_token=session_token,
            ):
                logger.info(
                    "glpi_session_retry_after_unauthorized",
                    extra={"method": method, "path": path, "multipart": True},
                )
                self._session_token = None
                return self._request_multipart(
                    method,
                    path,
                    files=files,
                    allow_session_retry=False,
                )
            safe_body = self._redact(str(exc.response.text))
            logger.warning(
                "glpi_multipart_http_status_error",
                extra={
                    "method": method,
                    "path": path,
                    "status_code": exc.response.status_code,
                    "body": safe_body,
                },
            )
            raise GLPIClientError("GLPI recusou o envio de anexo.") from exc
        except httpx.HTTPError as exc:
            logger.warning(
                "glpi_multipart_http_error",
                extra={"method": method, "path": path, "error": str(exc)},
            )
            raise GLPIClientError("Nao foi possivel enviar anexo ao GLPI.") from exc

        if not response.content:
            return {}
        payload = response.json()
        if isinstance(payload, list):
            return {"items": payload}
        return payload

    def _should_retry_after_unauthorized(
        self,
        exc: httpx.HTTPStatusError,
        *,
        use_session: bool,
        allow_session_retry: bool,
        session_token: str | None,
    ) -> bool:
        if exc.response.status_code != 401:
            return False
        if not use_session or not allow_session_retry:
            return False
        if self._is_initializing_session:
            return False
        return bool(session_token)

    def _ensure_base_url_allowed(self) -> None:
        if self.base_url.startswith("https://"):
            return
        if self.base_url.startswith("http://") and self.config.allow_insecure_http:
            return
        raise GLPIClientError(
            "GLPI_BASE_URL deve usar HTTPS em modo real, ou GLPI_ALLOW_INSECURE_HTTP=true para ambiente legado."
        )

    def _activate_profile_and_entity(self) -> None:
        if self.config.default_profile_id:
            self._request(
                "POST",
                "/changeActiveProfile",
                json={"profiles_id": self.config.default_profile_id},
            )
        if self.config.default_entity_id:
            self._request(
                "POST",
                "/changeActiveEntities",
                json={
                    "entities_id": self.config.default_entity_id,
                    "is_recursive": True,
                },
            )

    def _attach_documents(self, ticket_id: int, attachments: list[dict]) -> list[str]:
        errors: list[str] = []
        for index, attachment in enumerate(attachments, start=1):
            file_name = str(attachment.get("file_name") or f"anexo-{index}")
            try:
                raw_bytes = base64.b64decode(str(attachment.get("data_base64") or ""))
                mime_type = str(attachment.get("mime_type") or "application/octet-stream")
                manifest = {
                    "input": {
                        "name": file_name,
                        "_filename": [file_name],
                    }
                }
                response = self._request_multipart(
                    "POST",
                    "/Document",
                    files={
                        "uploadManifest": (
                            None,
                            jsonlib.dumps(manifest),
                            "application/json",
                        ),
                        "filename[0]": (file_name, raw_bytes, mime_type),
                    },
                )
                document_id = int(
                    response.get("id") or response.get("item", {}).get("id") or 0
                )
                if not document_id:
                    raise GLPIClientError("GLPI nao retornou ID do documento.")
                self._request(
                    "POST",
                    "/Document_Item",
                    json={
                        "input": {
                            "documents_id": document_id,
                            "itemtype": "Ticket",
                            "items_id": ticket_id,
                        }
                    },
                )
            except Exception:
                logger.exception(
                    "glpi_attachment_upload_failed",
                    extra={"ticket_id": ticket_id, "file_name": file_name},
                )
                errors.append(file_name)
        return errors

    def _create_attachment_failure_followup(
        self,
        ticket_id: int,
        attachment_errors: list[str],
    ) -> None:
        try:
            self._request(
                "POST",
                "/ITILFollowup",
                json={
                    "input": {
                        "itemtype": "Ticket",
                        "items_id": ticket_id,
                        "content": (
                            "Aviso automatico do bot: o chamado foi criado, mas nao foi "
                            "possivel anexar os seguintes arquivos: "
                            + ", ".join(attachment_errors)
                        ),
                        "is_private": 0,
                    }
                },
            )
        except GLPIClientError:
            logger.exception(
                "glpi_attachment_failure_followup_failed",
                extra={"ticket_id": ticket_id},
            )

    def _search_ticket_ids_for_requester(self, user_id: int) -> list[int]:
        response = self._request(
            "GET",
            "/search/Ticket",
            params={
                "criteria[0][field]": self.config.ticket_requester_search_field,
                "criteria[0][searchtype]": "equals",
                "criteria[0][value]": user_id,
                "forcedisplay[0]": 2,
                "sort": 2,
                "order": "DESC",
                "range": "0-9",
            },
        )
        rows = response.get("data", [])
        ticket_ids: list[int] = []
        for row in rows:
            ticket_id = self._extract_int_from_row(row, preferred_keys=("2", "id"))
            if ticket_id:
                ticket_ids.append(ticket_id)
        return ticket_ids

    def _ticket_belongs_to_user(
        self, ticket_id: int, ticket_data: dict, user_id: int
    ) -> bool:
        direct_user_fields = (
            "users_id_recipient",
            "_users_id_requester",
            "users_id_requester",
        )
        for field_name in direct_user_fields:
            if int(ticket_data.get(field_name) or 0) == user_id:
                return True

        try:
            response = self._request("GET", f"/Ticket/{ticket_id}/Ticket_User")
        except GLPIClientError:
            return False

        for item in response.get("items", []):
            if int(item.get("users_id") or 0) == user_id:
                return True
        return False

    def _ticket_from_glpi(self, ticket_data: dict, user_id: int) -> TicketCreated:
        ticket_number = int(ticket_data.get("id") or 0)
        return TicketCreated(
            ticket_number=ticket_number,
            title=str(ticket_data.get("name") or f"Chamado #{ticket_number}"),
            status=self._status_from_glpi(ticket_data.get("status")),
            severity=self._priority_to_severity(ticket_data.get("priority")),
            description=self._strip_html(str(ticket_data.get("content") or "")),
            category_name=str(ticket_data.get("itilcategories_id") or "GLPI"),
            requester_login=str(user_id),
            glpi_user_id=user_id,
            channel="glpi",
            location=str(ticket_data.get("locations_id") or ""),
            impact_label=str(ticket_data.get("impact") or ""),
            evidence="",
            opening_mode="Abertura assistida",
            created_at=str(ticket_data.get("date") or DateTimeProvider.utc_now_iso()),
        )

    @staticmethod
    def _created_ticket_from_payload(
        ticket_id: int,
        ticket_data: dict,
        attachments_expected_count: int = 0,
        attachments_uploaded_count: int = 0,
        attachment_errors: list[str] | None = None,
    ) -> TicketCreated:
        return TicketCreated(
            ticket_number=ticket_id,
            title=ticket_data["title"],
            status=TicketStatus.OPEN.value,
            severity=ticket_data["severity"],
            description=ticket_data["description"],
            category_name=ticket_data["category_name"],
            requester_login=ticket_data["requester_login"],
            glpi_user_id=int(ticket_data["glpi_user_id"]),
            channel=ticket_data["channel"],
            location=ticket_data["location"],
            impact_label=ticket_data["impact_label"],
            evidence=ticket_data.get("evidence") or "Não informado",
            opening_mode=ticket_data["opening_mode"],
            created_at=DateTimeProvider.utc_now_iso(),
            attachments_expected_count=attachments_expected_count,
            attachments_uploaded_count=attachments_uploaded_count,
            attachment_errors=attachment_errors or [],
        )

    @staticmethod
    def _status_from_glpi(raw_status: Any) -> str:
        status = int(raw_status or 0)
        if status == 1:
            return TicketStatus.OPEN.value
        if status in {2, 3, 4}:
            return TicketStatus.IN_PROGRESS.value
        if status in {5, 6}:
            return TicketStatus.CLOSED.value
        return TicketStatus.OPEN.value

    @staticmethod
    def _priority_to_severity(raw_priority: Any) -> str:
        priority = int(raw_priority or 0)
        if priority <= 2:
            return "Baixa"
        if priority == 3:
            return "Média"
        if priority == 4:
            return "Alta"
        return "Crítica"

    @staticmethod
    def _strip_html(text: str) -> str:
        return (
            text.replace("<p>", "")
            .replace("</p>", "\n")
            .replace("<br>", "\n")
            .replace("<br />", "\n")
            .strip()
        )

    @staticmethod
    def _extract_int_from_row(
        row: dict[str, Any], preferred_keys: tuple[str, ...]
    ) -> int | None:
        for key in preferred_keys:
            value = row.get(key)
            if isinstance(value, dict):
                value = value.get("value")
            try:
                if value is not None:
                    return int(value)
            except (TypeError, ValueError):
                continue
        return None

    def _redact(self, value: str) -> str:
        redacted = value
        if self.config.app_token:
            redacted = redacted.replace(self.config.app_token, "[APP_TOKEN_REDACTED]")
        if self.config.user_token:
            redacted = redacted.replace(self.config.user_token, "[USER_TOKEN_REDACTED]")
        if self._session_token:
            redacted = redacted.replace(
                self._session_token,
                "[SESSION_TOKEN_REDACTED]",
            )
        return redacted


GLPIFutureRealClient = GLPIRealClient
