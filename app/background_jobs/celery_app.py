from celery import Celery

from app.application_config.settings import load_settings


settings = load_settings()

celery_app = Celery(
    "assistente_chamados_ti",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["app.background_jobs.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="America/Cuiaba",
    enable_utc=True,
    task_track_started=True,
    broker_connection_retry_on_startup=True,
    task_always_eager=settings.celery_task_always_eager,
    task_eager_propagates=True,
    worker_prefetch_multiplier=1,
    task_routes={
        "app.background_jobs.tasks.organize_description_task": {
            "queue": settings.ai_queue_name
        },
        "app.background_jobs.tasks.detail_ticket_description_task": {
            "queue": settings.ai_queue_name
        },
        "app.background_jobs.tasks.create_glpi_ticket_task": {
            "queue": settings.glpi_queue_name
        },
        "app.background_jobs.tasks.query_glpi_tickets_task": {
            "queue": settings.glpi_queue_name
        },
        "app.background_jobs.tasks.get_glpi_ticket_task": {
            "queue": settings.glpi_queue_name
        },
        "app.background_jobs.tasks.add_glpi_followup_task": {
            "queue": settings.glpi_queue_name
        },
        "app.background_jobs.tasks.validate_glpi_mapping_task": {
            "queue": settings.glpi_queue_name
        },
    },
)
