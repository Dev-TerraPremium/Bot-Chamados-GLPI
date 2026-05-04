import re


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
        return text.strip() in {"", "__start__"}

