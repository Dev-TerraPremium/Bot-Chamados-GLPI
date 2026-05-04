class WhatsAppFutureAdapter:
    """Future WhatsApp adapter.

    Business rules must remain in conversation_engine. This adapter should only
    normalize provider webhooks and map channel identities.
    """

    def receive_webhook(self, payload: dict):
        raise NotImplementedError("WhatsApp integration is not implemented in this MVP.")

