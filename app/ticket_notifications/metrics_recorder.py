from __future__ import annotations

import logging
import time
from contextlib import contextmanager
from typing import Iterator

logger = logging.getLogger(__name__)


class NotificationMetricsRecorder:
    KEY_PREFIX = "ticket_notifications:metrics"

    def __init__(self, redis_client=None) -> None:
        self.redis_client = redis_client

    def increment(self, metric: str, value: int = 1) -> None:
        if self.redis_client is None:
            return
        try:
            self.redis_client.hincrby(self.KEY_PREFIX, metric, value)
        except Exception:
            logger.exception("ticket_notification_metric_increment_failed")

    def gauge(self, metric: str, value: int | float) -> None:
        if self.redis_client is None:
            return
        try:
            self.redis_client.hset(self.KEY_PREFIX, metric, value)
        except Exception:
            logger.exception("ticket_notification_metric_gauge_failed")

    def observe_ms(self, metric: str, value_ms: int) -> None:
        if self.redis_client is None:
            return
        try:
            pipe = self.redis_client.pipeline()
            pipe.hset(self.KEY_PREFIX, metric, value_ms)
            pipe.hincrby(self.KEY_PREFIX, f"{metric}_samples", 1)
            pipe.execute()
        except Exception:
            logger.exception("ticket_notification_metric_observe_failed")

    @contextmanager
    def measure(self, metric: str) -> Iterator[None]:
        started_at = time.perf_counter()
        try:
            yield
        finally:
            self.observe_ms(metric, int((time.perf_counter() - started_at) * 1000))

    def snapshot(self) -> dict[str, str]:
        if self.redis_client is None:
            return {}
        try:
            return dict(self.redis_client.hgetall(self.KEY_PREFIX))
        except Exception:
            logger.exception("ticket_notification_metric_snapshot_failed")
            return {}
