from dataclasses import asdict

from app.application_config.settings import load_settings
from app.background_jobs.celery_app import celery_app
from app.glpi_integration_reserved.glpi_future_real_client import GLPIRealClient
from app.glpi_integration_reserved.glpi_integration_config import GLPIIntegrationConfig
from app.local_light_ai.generative_description_organizer import (
    build_generative_description_organizer,
)


def _build_real_glpi_client() -> GLPIRealClient:
    settings = load_settings()
    return GLPIRealClient(
        GLPIIntegrationConfig(
            base_url=settings.glpi_base_url,
            app_token=settings.glpi_app_token,
            user_token=settings.glpi_user_token,
            integration_mode=settings.glpi_integration_mode,
            default_entity_id=settings.glpi_default_entity_id,
            default_profile_id=settings.glpi_default_profile_id,
            default_requester_user_id=settings.glpi_default_requester_user_id,
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
) -> dict:
    organizer = build_generative_description_organizer(load_settings())
    return asdict(organizer.organize_ticket_description(
        user_text=user_text,
        category_name=category_name,
        purpose=purpose,
    ))


@celery_app.task(
    name="app.background_jobs.tasks.create_glpi_ticket_task",
    autoretry_for=(ConnectionError, TimeoutError),
    retry_backoff=True,
    max_retries=2,
    soft_time_limit=20,
    time_limit=30,
)
def create_glpi_ticket_task(ticket_data: dict) -> dict:
    return _build_real_glpi_client().create_ticket(ticket_data).to_dict()


@celery_app.task(
    name="app.background_jobs.tasks.query_glpi_tickets_task",
    autoretry_for=(ConnectionError, TimeoutError),
    retry_backoff=True,
    max_retries=2,
    soft_time_limit=20,
    time_limit=30,
)
def query_glpi_tickets_task(user_id: int) -> list[dict]:
    return [
        ticket.to_dict()
        for ticket in _build_real_glpi_client().get_my_tickets(user_id)
    ]


@celery_app.task(
    name="app.background_jobs.tasks.get_glpi_ticket_task",
    autoretry_for=(ConnectionError, TimeoutError),
    retry_backoff=True,
    max_retries=2,
    soft_time_limit=20,
    time_limit=30,
)
def get_glpi_ticket_task(ticket_id: int, user_id: int) -> dict | None:
    ticket = _build_real_glpi_client().get_ticket_by_id(ticket_id, user_id)
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
    followup = _build_real_glpi_client().add_followup(ticket_id, user_id, content)
    return None if followup is None else followup.to_dict()


@celery_app.task(
    name="app.background_jobs.tasks.validate_glpi_mapping_task",
    soft_time_limit=20,
    time_limit=30,
)
def validate_glpi_mapping_task(category_name: str) -> dict | None:
    return _build_real_glpi_client().find_category_by_name(category_name)
