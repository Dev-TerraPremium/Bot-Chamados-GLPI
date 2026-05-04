class TelegramFutureAdapter:
    """Future Telegram adapter.

    Business rules must remain in conversation_engine. This adapter should only
    translate Telegram updates into normalized messages and return bot text.
    """

    def receive_update(self, update: dict):
        raise NotImplementedError("Telegram integration is not implemented in this MVP.")

