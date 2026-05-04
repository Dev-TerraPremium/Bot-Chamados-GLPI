import re


class InputSanitizer:
    def sanitize(self, text: str) -> str:
        cleaned = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
        cleaned = cleaned.replace("<", "").replace(">", "")
        cleaned = re.sub(r"\s+", " ", cleaned)
        return cleaned.strip()

