class MessageSizeLimiter:
    def __init__(self, max_length: int = 1000) -> None:
        self.max_length = max_length

    def ensure_allowed(self, text: str) -> None:
        if len(text) > self.max_length:
            raise ValueError(
                f"Mensagem excede o limite de {self.max_length} caracteres."
            )

