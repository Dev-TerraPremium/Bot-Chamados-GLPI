from fastapi import APIRouter

from app.application_config.settings import load_settings
from app.distributed_runtime.redis_connection import get_redis_client
from app.ticket_notifications.metrics_recorder import NotificationMetricsRecorder


router = APIRouter(prefix="/api/notification-metrics", tags=["notification-metrics"])


@router.get("")
def notification_metrics() -> dict:
    settings = load_settings()
    if not settings.is_redis_state_enabled:
        return {"enabled": settings.ticket_notifications_enabled, "metrics": {}}
    metrics = NotificationMetricsRecorder(get_redis_client(settings.redis_url))
    return {
        "enabled": settings.ticket_notifications_enabled,
        "poll_interval_seconds": settings.ticket_notification_poll_interval_seconds,
        "metrics": metrics.snapshot(),
    }
