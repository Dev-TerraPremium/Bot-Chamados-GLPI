import logging
import sys


class StructuredLogFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        base = {
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if hasattr(record, "session_id"):
            base["session_id"] = getattr(record, "session_id")
        if hasattr(record, "state"):
            base["state"] = getattr(record, "state")
        return str(base)


def configure_logging() -> None:
    root_logger = logging.getLogger()
    if root_logger.handlers:
        return

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(StructuredLogFormatter())
    root_logger.addHandler(handler)
    root_logger.setLevel(logging.INFO)

