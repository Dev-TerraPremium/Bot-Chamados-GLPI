from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class DescriptionOrganizationResult:
    status: str
    organized_text: str
    clarification_question: str
    confidence: float
    backend: str

    @property
    def is_organized(self) -> bool:
        return self.status == "organized" and bool(self.organized_text.strip())

    @property
    def needs_clarification(self) -> bool:
        return self.status == "needs_clarification"


@dataclass(frozen=True, slots=True)
class GuidedDetailingResult:
    status: str
    next_question: str
    organized_text: str
    confidence: float
    backend: str

    @property
    def asks_next(self) -> bool:
        return self.status == "ask_next" and bool(self.next_question.strip())

    @property
    def is_ready(self) -> bool:
        return self.status == "ready"


class LocalGenerativeAIUnavailableError(RuntimeError):
    """Raised when the local generative runtime cannot be reached."""
