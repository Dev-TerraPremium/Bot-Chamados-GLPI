from __future__ import annotations

import logging

from app.application_config.settings import load_settings
from app.ticket_notifications.factory import build_notification_pipeline

logger = logging.getLogger(__name__)


def run_ticket_notification_poll_cycle() -> dict[str, int]:
    settings = load_settings()
    if not settings.ticket_notifications_enabled:
        return {"watched": 0, "captured": 0, "sent": 0, "ignored": 0, "failed": 0}
    if not settings.is_glpi_real_mode:
        logger.info("ticket_notification_poll_skipped_non_real_glpi")
        return {"watched": 0, "captured": 0, "sent": 0, "ignored": 0, "failed": 0}
    pipeline = build_notification_pipeline(settings)
    summary = pipeline.run_once()
    logger.info("ticket_notification_poll_completed", extra=summary)
    return summary
