from dataclasses import dataclass

from app.conversation_engine.conversation_input_parser import ConversationInputParser


@dataclass(frozen=True, slots=True)
class MenuValidationResult:
    is_valid: bool
    choice: int | None
    message: str


class ConversationMenuValidator:
    def __init__(self, parser: ConversationInputParser | None = None) -> None:
        self.parser = parser or ConversationInputParser()

    def require_choice(
        self,
        raw_message: str,
        allowed_choices: set[int],
    ) -> MenuValidationResult:
        choice = self.parser.parse_choice(raw_message)
        if choice is None:
            return MenuValidationResult(
                is_valid=False,
                choice=None,
                message="⚠️ Opção inválida. Responda só com o número de uma das opções.",
            )
        if choice not in allowed_choices:
            allowed = ", ".join(str(item) for item in sorted(allowed_choices))
            return MenuValidationResult(
                is_valid=False,
                choice=choice,
                message=(
                    "⚠️ Essa opção não está disponível neste menu. "
                    f"Escolha uma destas opções: **{allowed}**."
                ),
            )
        return MenuValidationResult(is_valid=True, choice=choice, message="")
