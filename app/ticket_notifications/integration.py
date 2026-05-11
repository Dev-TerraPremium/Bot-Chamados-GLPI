from __future__ import annotations

import logging
from typing import Any

from app.application_config.settings import AppSettings
from app.distributed_runtime.redis_connection import get_redis_client
from app.ticket_notifications.event_store import TicketNotificationStore
from app.ticket_notifications.message_renderer import TicketNotificationMessageRenderer
from app.ticket_notifications.metrics_recorder import NotificationMetricsRecorder
from app.ticket_notifications.models import WatchedTicket
from app.ticket_notifications.whatsapp_dispatcher import WhatsAppNotificationDispatcher

logger = logging.getLogger(__name__)


def register_ticket_opened_for_notifications(
    *,
    settings: AppSettings,
    context,
    created_ticket: dict[str, Any],
) -> None:
    if not settings.ticket_notifications_enabled:
        return
    if not settings.is_redis_state_enabled:
        logger.warning("ticket_notification_disabled_without_redis")
        return

    ticket_id = int(created_ticket.get("ticket_number") or 0)
    if not ticket_id:
        return

    redis_client = get_redis_client(settings.redis_url)
    store = TicketNotificationStore(
        redis_client,
        watch_ttl_days=settings.ticket_notification_watch_ttl_days,
    )
    watched_ticket = WatchedTicket(
        ticket_id=ticket_id,
        requester_phone=context.session_id if context.channel == "whatsapp" else "",
        requester_name=context.user.full_name,
        requester_login=context.user.login,
        category_name=str(created_ticket.get("category_name") or ""),
        title=str(created_ticket.get("title") or ""),
        location=str(created_ticket.get("location") or ""),
        created_at=str(created_ticket.get("created_at") or ""),
        channel=context.channel,
    )
    store.watch_ticket(watched_ticket)
    metrics = NotificationMetricsRecorder(redis_client)
    metrics.increment("tickets_watched")
    logger.info(
        "ticket_notification_watch_registered",
        extra={"ticket_id": ticket_id, "channel": context.channel},
    )
    _send_internal_ticket_opened_notification(settings, watched_ticket, created_ticket, metrics)


def _send_internal_ticket_opened_notification(
    settings: AppSettings,
    watched_ticket: WatchedTicket,
    created_ticket: dict[str, Any],
    metrics: NotificationMetricsRecorder,
) -> None:
    numbers = _split_numbers(settings.ticket_notification_internal_numbers)
    if not numbers:
        return

    dispatcher = WhatsAppNotificationDispatcher(
        base_url=settings.whatsapp_outbound_base_url,
        internal_token=settings.whatsapp_internal_api_token,
        timeout_seconds=settings.ticket_notification_dispatch_timeout_seconds,
    )
    renderer = TicketNotificationMessageRenderer(
        ticket_url_template=settings.glpi_ticket_public_url_template
    )
    message = renderer.render_internal_ticket_opened(watched_ticket, created_ticket)
    for number in numbers:
        result = dispatcher.send_message(number, message)
        if result.ok:
            metrics.increment("internal_notifications_sent")
        else:
            metrics.increment("internal_notifications_failed")


def _split_numbers(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]
