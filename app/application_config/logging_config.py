import logging
import sys


STRUCTURED_EXTRA_FIELDS = (
    "session_id",
    "state",
    "purpose",
    "queue_wait_ms",
    "task_duration_ms",
    "google_attempt",
    "google_attempts",
    "google_duration_ms",
    "status_code",
    "model",
    "usageMetadata",
    "backend",
    "status",
    "task",
    "category_id",
    "category_source",
    "confidence",
    "method",
    "path",
    "ticket_id",
    "itemtype",
    "consecutive_failures",
    "events",
    "event_types",
    "error",
    "body",
)


class StructuredLogFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        base = {
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for field in STRUCTURED_EXTRA_FIELDS:
            if hasattr(record, field):
                base[field] = getattr(record, field)
        return str(base)


def configure_logging() -> None:
    root_logger = logging.getLogger()
    formatter = StructuredLogFormatter()
    if root_logger.handlers:
        for handler in root_logger.handlers:
            handler.setFormatter(formatter)
        root_logger.setLevel(logging.INFO)
        return

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    root_logger.addHandler(handler)
    root_logger.setLevel(logging.INFO)
