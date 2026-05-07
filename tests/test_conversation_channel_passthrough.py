from app.channel_adapters.web_simulator_adapter import WebSimulatorAdapter


class RecordingFlowController:
    def __init__(self) -> None:
        self.calls = []

    def process_message(self, **kwargs):
        self.calls.append(("message", kwargs))
        return type(
            "Result",
            (),
            {
                "session_id": kwargs["session_id"],
                "bot_message": "ok",
                "state": "ok",
                "ticket_preview": None,
                "created_ticket": None,
            },
        )()

    def reset_conversation(self, **kwargs):
        self.calls.append(("reset", kwargs))
        return type(
            "Result",
            (),
            {
                "session_id": kwargs["session_id"],
                "bot_message": "ok",
                "state": "ok",
                "ticket_preview": None,
                "created_ticket": None,
            },
        )()


def test_adapter_preserves_whatsapp_channel_for_authentication_scope() -> None:
    controller = RecordingFlowController()
    adapter = WebSimulatorAdapter(controller)

    adapter.receive_message(
        session_id="s1",
        message="Olá",
        channel="whatsapp",
        channel_identifier="66999990980",
    )

    assert controller.calls[0][1]["channel"] == "whatsapp"


def test_adapter_preserves_whatsapp_channel_on_reset() -> None:
    controller = RecordingFlowController()
    adapter = WebSimulatorAdapter(controller)

    adapter.reset_session(
        session_id="s1",
        channel="whatsapp",
        channel_identifier="66999990980",
    )

    assert controller.calls[0][1]["channel"] == "whatsapp"
