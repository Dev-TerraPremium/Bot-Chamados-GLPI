from fastapi import APIRouter

from app.channel_adapters.web_simulator_adapter import WebSimulatorAdapter
from app.conversation_engine.conversation_flow_controller import (
    ConversationFlowController,
)
from app.shared_kernel.common_response_models import (
    ConversationMessageRequest,
    ConversationMessageResponse,
)


router = APIRouter(prefix="/api/conversation", tags=["conversation"])
debug_router = APIRouter(prefix="/api/debug", tags=["debug"])

flow_controller = ConversationFlowController()
web_adapter = WebSimulatorAdapter(flow_controller)


def _to_response(result) -> ConversationMessageResponse:
    return ConversationMessageResponse(
        session_id=result.session_id,
        bot_message=result.bot_message,
        state=result.state,
        ticket_preview=result.ticket_preview,
        created_ticket=result.created_ticket,
    )


@router.post("/message", response_model=ConversationMessageResponse)
def send_message(request: ConversationMessageRequest) -> ConversationMessageResponse:
    result = web_adapter.receive_message(
        session_id=request.session_id,
        message=request.message,
        channel=request.channel,
        channel_identifier=request.channel_identifier,
        media=[m.to_context_dict() for m in request.media] if request.media else None
    )
    return _to_response(result)


@router.post("/reset", response_model=ConversationMessageResponse)
def reset_conversation(
    request: ConversationMessageRequest,
) -> ConversationMessageResponse:
    result = web_adapter.reset_session(
        session_id=request.session_id,
        channel=request.channel,
        channel_identifier=request.channel_identifier,
    )
    return _to_response(result)


@debug_router.get("/session/{session_id}")
def debug_session(session_id: str):
    return flow_controller.debug_session(session_id) or {"detail": "session_not_found"}
