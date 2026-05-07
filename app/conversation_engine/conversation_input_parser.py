import re
import unicodedata


class ConversationInputParser:
    RESET_COMMANDS = {"/reset", "reset", "reiniciar", "menu", "cancelar"}

    def parse_choice(self, text: str) -> int | None:
        match = re.fullmatch(r"\s*(\d{1,4})\s*", text)
        if not match:
            return None
        return int(match.group(1))

    def parse_ticket_number(self, text: str) -> int | None:
        match = re.search(r"\d{3,10}", text)
        if not match:
            return None
        return int(match.group(0))

    def is_reset_command(self, text: str) -> bool:
        return text.strip().casefold() in self.RESET_COMMANDS

    def is_start_message(self, text: str) -> bool:
        normalized = self._normalize_control_text(text)
        return normalized in {
            "",
            "__start__",
            "oi",
            "ola",
            "olá",
            "bom dia",
            "boa tarde",
            "boa noite",
            "menu",
            "inicio",
            "iniciar",
        }

    @staticmethod
    def _normalize_control_text(text: str) -> str:
        normalized = unicodedata.normalize("NFKD", text.casefold().strip())
        normalized = "".join(
            char for char in normalized if not unicodedata.combining(char)
        )
        normalized = re.sub(r"[^\w\s_]", " ", normalized)
        return re.sub(r"\s+", " ", normalized).strip()
