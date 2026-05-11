from dataclasses import asdict
import logging
import time

from app.application_config.settings import load_settings
from app.background_jobs.celery_app import celery_app
from app.glpi_integration_reserved.glpi_mock_client import GLPIMockClient
from app.glpi_integration_reserved.glpi_future_real_client import GLPIRealClient
from app.glpi_integration_reserved.glpi_integration_config import GLPIIntegrationConfig
from app.local_light_ai.generative_description_organizer import (
    build_generative_description_organizer,
)
from app.local_light_ai.guided_ticket_detailer import build_guided_ticket_detailer
from app.simulated_persistence.in_memory_ticket_store import InMemoryTicketStore
from app.ticket_notifications.tasks import run_ticket_notification_poll_cycle


worker_ticket_store = InMemoryTicketStore()
logger = logging.getLogger(__name__)


def _queue_wait_ms(enqueued_at: float | None) -> int:
    if enqueued_at is None:
        return 0
    return max(0, int((time.time() - enqueued_at) * 1000))


def _build_glpi_client():
    settings = load_settings()
    if not settings.is_glpi_real_mode:
        return GLPIMockClient(worker_ticket_store)

    return GLPIRealClient(
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
    )


@celery_app.task(
    name="app.background_jobs.tasks.organize_description_task",
    soft_time_limit=25,
    time_limit=30,
)
def organize_description_task(
    user_text: str,
    category_name: str | None,
    purpose: str,
    enqueued_at: float | None = None,
) -> dict:
    started_at = time.perf_counter()
    queue_wait_ms = _queue_wait_ms(enqueued_at)
    logger.info(
        "ai_task_started",
        extra={
            "purpose": purpose,
            "queue_wait_ms": queue_wait_ms,
            "task": "organize_description_task",
        },
    )
    organizer = build_generative_description_organizer(load_settings())
    try:
        result = asdict(
            organizer.organize_ticket_description(
                user_text=user_text,
                category_name=category_name,
                purpose=purpose,
            )
        )
    except Exception:
        logger.exception(
            "ai_task_failed",
            extra={
                "purpose": purpose,
                "queue_wait_ms": queue_wait_ms,
                "task_duration_ms": int((time.perf_counter() - started_at) * 1000),
                "task": "organize_description_task",
            },
        )
        raise
    logger.info(
        "ai_task_completed",
        extra={
            "purpose": purpose,
            "queue_wait_ms": queue_wait_ms,
            "task_duration_ms": int((time.perf_counter() - started_at) * 1000),
            "task": "organize_description_task",
        },
    )
    return result


@celery_app.task(
    name="app.background_jobs.tasks.detail_ticket_description_task",
    soft_time_limit=25,
    time_limit=30,
)
def detail_ticket_description_task(
    original_description: str,
    clarification_turns: list[dict[str, str]],
    category_name: str | None,
    max_questions: int,
    enqueued_at: float | None = None,
) -> dict:
    started_at = time.perf_counter()
    queue_wait_ms = _queue_wait_ms(enqueued_at)
    logger.info(
        "ai_task_started",
        extra={
            "purpose": "descricao_chamado_pergunta_guiada",
            "queue_wait_ms": queue_wait_ms,
            "task": "detail_ticket_description_task",
        },
    )
    detailer = build_guided_ticket_detailer(load_settings())
    try:
        result = asdict(
            detailer.detail_ticket_description(
                original_description=original_description,
                clarification_turns=clarification_turns,
                category_name=category_name,
                max_questions=max_questions,
            )
        )
    except Exception:
        logger.exception(
            "ai_task_failed",
            extra={
                "purpose": "descricao_chamado_pergunta_guiada",
                "queue_wait_ms": queue_wait_ms,
                "task_duration_ms": int((time.perf_counter() - started_at) * 1000),
                "task": "detail_ticket_description_task",
            },
        )
        raise
    logger.info(
        "ai_task_completed",
        extra={
            "purpose": "descricao_chamado_pergunta_guiada",
            "queue_wait_ms": queue_wait_ms,
            "task_duration_ms": int((time.perf_counter() - started_at) * 1000),
            "task": "detail_ticket_description_task",
        },
    )
    return result


@celery_app.task(
    name="app.background_jobs.tasks.create_glpi_ticket_task",
    autoretry_for=(ConnectionError, TimeoutError),
    retry_backoff=True,
    max_retries=2,
    soft_time_limit=20,
    time_limit=30,
)
def create_glpi_ticket_task(ticket_data: dict) -> dict:
    return _build_glpi_client().create_ticket(ticket_data).to_dict()


@celery_app.task(
    name="app.background_jobs.tasks.query_glpi_tickets_task",
    autoretry_for=(ConnectionError, TimeoutError),
    retry_backoff=True,
    max_retries=2,
    soft_time_limit=20,
    time_limit=30,
)
def query_glpi_tickets_task(user_id: int) -> list[dict]:
    return [ticket.to_dict() for ticket in _build_glpi_client().get_my_tickets(user_id)]


@celery_app.task(
    name="app.background_jobs.tasks.get_glpi_ticket_task",
    autoretry_for=(ConnectionError, TimeoutError),
    retry_backoff=True,
    max_retries=2,
    soft_time_limit=20,
    time_limit=30,
)
def get_glpi_ticket_task(ticket_id: int, user_id: int) -> dict | None:
    ticket = _build_glpi_client().get_ticket_by_id(ticket_id, user_id)
    return None if ticket is None else ticket.to_dict()


@celery_app.task(
    name="app.background_jobs.tasks.add_glpi_followup_task",
    autoretry_for=(ConnectionError, TimeoutError),
    retry_backoff=True,
    max_retries=2,
    soft_time_limit=20,
    time_limit=30,
)
def add_glpi_followup_task(ticket_id: int, user_id: int, content: str) -> dict | None:
    followup = _build_glpi_client().add_followup(ticket_id, user_id, content)
    return None if followup is None else followup.to_dict()


@celery_app.task(
    name="app.background_jobs.tasks.validate_glpi_mapping_task",
    soft_time_limit=20,
    time_limit=30,
)
def validate_glpi_mapping_task(category_name: str) -> dict | None:
    return _build_glpi_client().find_category_by_name(category_name)


@celery_app.task(
    name="app.background_jobs.tasks.poll_ticket_notifications_task",
    soft_time_limit=25,
    time_limit=30,
)
def poll_ticket_notifications_task() -> dict:
    return run_ticket_notification_poll_cycle()
