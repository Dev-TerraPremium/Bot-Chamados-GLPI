class MicrosoftTeamsFutureAdapter:
    """Future Microsoft Teams adapter.

    Business rules must remain in conversation_engine. This adapter should only
    translate Teams activities into normalized conversation engine calls.
    """

    def receive_activity(self, activity: dict):
        raise NotImplementedError(
            "Microsoft Teams integration is not implemented in this MVP."
        )

