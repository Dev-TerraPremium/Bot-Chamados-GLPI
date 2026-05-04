from datetime import datetime, timezone


class DateTimeProvider:
    """Centralizes time generation for easier replacement in tests."""

    @staticmethod
    def utc_now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()

