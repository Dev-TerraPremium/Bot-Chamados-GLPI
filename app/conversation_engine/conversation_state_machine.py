from app.conversation_engine.conversation_context import ConversationContext
from app.conversation_engine.conversation_states import ConversationState


class ConversationStateMachine:
    def transition_to(
        self, context: ConversationContext, new_state: ConversationState
    ) -> None:
        context.state = new_state

