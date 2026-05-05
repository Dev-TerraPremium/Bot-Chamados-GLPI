from app.conversation_engine.conversation_flow_controller import (
    ConversationFlowController,
)
from app.shared_kernel.constants import DEFAULT_CHANNEL
from app.shared_kernel.result_types import ConversationTurnResult


class WebSimulatorAdapter:
    """Adapter used by the temporary HTML web simulator."""

    def __init__(self, flow_controller: ConversationFlowController) -> None:
        self.flow_controller = flow_controller

    def receive_message(
        self, session_id: str, message: str, channel_identifier: str = "", media: list[dict] | None = None
    ) -> ConversationTurnResult:
        return self.flow_controller.process_message(
            session_id=session_id,
            message=message,
            channel=DEFAULT_CHANNEL,
            channel_identifier=channel_identifier,
            media=media,
        )

    def reset_session(self, session_id: str, channel_identifier: str = "") -> ConversationTurnResult:
        return self.flow_controller.reset_conversation(
            session_id=session_id,
            channel=DEFAULT_CHANNEL,
            channel_identifier=channel_identifier,
        )

