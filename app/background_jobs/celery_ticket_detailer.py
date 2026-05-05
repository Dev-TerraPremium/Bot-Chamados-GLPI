from celery.exceptions import CeleryError, TimeoutError as CeleryTimeoutError

from app.application_config.settings import AppSettings
from app.background_jobs.tasks import detail_ticket_description_task
from app.local_light_ai.description_organization_models import (
    GuidedDetailingResult,
    LocalGenerativeAIUnavailableError,
)


class CeleryTicketDetailer:
    def __init__(self, settings: AppSettings) -> None:
        self.settings = settings

    def detail_ticket_description(
        self,
        original_description: str,
        clarification_turns: list[dict[str, str]],
        category_name: str | None,
        max_questions: int,
    ) -> GuidedDetailingResult:
        try:
            async_result = detail_ticket_description_task.apply_async(
                args=[
                    original_description,
                    clarification_turns,
                    category_name,
                    max_questions,
                ],
                queue=self.settings.ai_queue_name,
            )
            payload = async_result.get(
                timeout=self.settings.ai_task_timeout_seconds,
                disable_sync_subtasks=False,
            )
        except (CeleryError, CeleryTimeoutError) as exc:
            raise LocalGenerativeAIUnavailableError(
                "A fila da IA local nao respondeu no tempo esperado."
            ) from exc

        return GuidedDetailingResult(
            status=payload["status"],
            next_question=payload["next_question"],
            organized_text=payload["organized_text"],
            confidence=float(payload["confidence"]),
            backend=payload["backend"],
        )
