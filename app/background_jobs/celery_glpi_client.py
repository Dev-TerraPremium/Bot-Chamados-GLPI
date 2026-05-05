from celery.exceptions import CeleryError, TimeoutError as CeleryTimeoutError

from app.application_config.settings import AppSettings
from app.background_jobs.tasks import (
    add_glpi_followup_task,
    create_glpi_ticket_task,
    get_glpi_ticket_task,
    query_glpi_tickets_task,
)
from app.glpi_integration_reserved.glpi_client_interface import GLPIClientInterface
from app.glpi_integration_reserved.glpi_future_real_client import GLPIClientError
from app.ticket_domain.ticket_models import TicketCreated, TicketFollowup


class CeleryGLPIClient(GLPIClientInterface):
    def __init__(self, settings: AppSettings) -> None:
        self.settings = settings

    def init_session(self) -> str:
        return "managed-by-glpi-worker"

    def kill_session(self) -> None:
        return None

    def create_ticket(self, ticket_data: dict) -> TicketCreated:
        payload = self._run_task(create_glpi_ticket_task, [ticket_data])
        return TicketCreated.from_dict(payload)

    def get_my_tickets(self, user_id: int) -> list[TicketCreated]:
        payload = self._run_task(query_glpi_tickets_task, [user_id])
        return [TicketCreated.from_dict(item) for item in payload]

    def get_ticket_by_id(self, ticket_id: int, user_id: int) -> TicketCreated | None:
        payload = self._run_task(get_glpi_ticket_task, [ticket_id, user_id])
        return None if payload is None else TicketCreated.from_dict(payload)

    def add_followup(
        self, ticket_id: int, user_id: int, content: str
    ) -> TicketFollowup | None:
        payload = self._run_task(add_glpi_followup_task, [ticket_id, user_id, content])
        return None if payload is None else TicketFollowup.from_dict(payload)

    def find_user_by_identifier(self, identifier: str):
        raise NotImplementedError("Use GLPIRealClient directly for user lookup.")

    def find_category_by_name(self, category_name: str):
        raise NotImplementedError("Use validate_glpi_mapping_task for category lookup.")

    def _run_task(self, task, args: list):
        try:
            async_result = task.apply_async(args=args, queue=self.settings.glpi_queue_name)
            return async_result.get(
                timeout=self.settings.glpi_task_timeout_seconds,
                disable_sync_subtasks=False,
            )
        except (CeleryError, CeleryTimeoutError) as exc:
            raise GLPIClientError(
                "A fila de integracao GLPI nao respondeu no tempo esperado."
            ) from exc
