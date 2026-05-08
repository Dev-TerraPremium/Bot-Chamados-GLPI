from celery.exceptions import CeleryError, TimeoutError as CeleryTimeoutError
import time

from app.application_config.settings import AppSettings
from app.background_jobs.tasks import organize_description_task
from app.local_light_ai.description_organization_models import (
    DescriptionOrganizationResult,
    LocalGenerativeAIUnavailableError,
)


class CeleryDescriptionOrganizer:
    def __init__(self, settings: AppSettings) -> None:
        self.settings = settings

    def organize_ticket_description(
        self,
        user_text: str,
        category_name: str | None = None,
        purpose: str = "descricao_chamado",
    ) -> DescriptionOrganizationResult:
        try:
            async_result = organize_description_task.apply_async(
                args=[user_text, category_name, purpose, time.time()],
                queue=self.settings.ai_queue_name,
            )
            payload = async_result.get(
                timeout=max(1, self.settings.ai_task_timeout_seconds - 1),
                disable_sync_subtasks=False,
            )
        except (CeleryError, CeleryTimeoutError) as exc:
            try:
                async_result.revoke()
            except Exception:
                pass
            raise LocalGenerativeAIUnavailableError(
                "A fila da IA local nao respondeu no tempo esperado."
            ) from exc

        return DescriptionOrganizationResult(
            status=payload["status"],
            organized_text=payload["organized_text"],
            clarification_question=payload["clarification_question"],
            confidence=float(payload["confidence"]),
            backend=payload["backend"],
        )
