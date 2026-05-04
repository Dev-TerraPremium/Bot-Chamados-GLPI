from app.conversation_engine.conversation_context import ConversationContext


class InMemoryConversationStore:
    def __init__(self) -> None:
        self._contexts: dict[str, ConversationContext] = {}

    def get(self, session_id: str) -> ConversationContext | None:
        return self._contexts.get(session_id)

    def save(self, context: ConversationContext) -> None:
        self._contexts[context.session_id] = context

    def delete(self, session_id: str) -> None:
        self._contexts.pop(session_id, None)

    def debug_context(self, session_id: str) -> dict | None:
        context = self.get(session_id)
        if context is None:
            return None
        return context.to_safe_dict()

