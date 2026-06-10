import re
from html import unescape


class TitleGenerationService:
    MAX_TITLE_CHARS = 64
    MAX_TITLE_WORDS = 10
    FALLBACK_TITLE = "Chamado de TI"

    def generate_title(self, category_name: str, description: str) -> str:
        source_text = self._normalize_source_text(description)
        if not source_text:
            return self.FALLBACK_TITLE

        candidate = self._first_meaningful_fragment(source_text)
        return self.clean_title(candidate, category_name)

    @classmethod
    def clean_title(cls, title: str, category_name: str = "") -> str:
        title = cls._normalize_source_text(title)
        title = cls._remove_category_prefix(title, category_name)
        title = cls._remove_leading_noise(title)
        title = cls._normalize_punctuation(title)
        title = cls._apply_common_terms(title)
        title = cls._limit_title(title)
        title = cls._ensure_professional_case(title)
        if cls._is_too_generic(title):
            return cls.FALLBACK_TITLE
        return title or cls.FALLBACK_TITLE

    @staticmethod
    def _normalize_source_text(text: str) -> str:
        text = unescape(str(text or ""))
        text = re.sub(r"<br\s*/?>", " ", text, flags=re.IGNORECASE)
        text = re.sub(r"<[^>]+>", " ", text)
        text = text.replace("\u00a0", " ")
        text = re.sub(r"[*_`~]+", "", text)
        text = re.sub(r"\s+", " ", text)
        return text.strip(" \t\r\n.:-")

    @classmethod
    def _remove_category_prefix(cls, title: str, category_name: str) -> str:
        category = cls._normalize_source_text(category_name)
        if category and title.casefold().startswith(category.casefold()):
            title = title[len(category) :].strip(" .:-")
        if " - " in title and ">" in title.split(" - ", maxsplit=1)[0]:
            title = title.split(" - ", maxsplit=1)[1].strip(" .:-")
        if ">" in title:
            title = title.split(">")[-1].strip(" .:-")
        return title

    @classmethod
    def _first_meaningful_fragment(cls, text: str) -> str:
        fragments = [
            fragment.strip(" .:-")
            for fragment in re.split(r"[.!?;\n\r]+", text)
            if fragment.strip(" .:-")
        ]
        for fragment in fragments:
            cleaned = cls._remove_leading_noise(fragment)
            if len(cleaned) >= 8 and not cls._is_too_generic(cleaned):
                return fragment
        return text

    @staticmethod
    def _remove_leading_noise(title: str) -> str:
        replacements = (
            r"^(?:o\s+)?usuario\s+(?:informa|informou|relata|relatou|reporta|reportou)\s+(?:que\s+)?",
            r"^(?:a\s+)?solicitante\s+(?:informa|informou|relata|relatou|reporta|reportou)\s+(?:que\s+)?",
            r"^venho\s+(?:por\s+meio\s+deste\s+)?solicitar\s+",
            r"^gostaria\s+de\s+(?:solicitar|pedir|informar)\s+",
            r"^preciso\s+de\s+",
            r"^necessito\s+de\s+",
            r"^solicito\s+(?:a\s+|o\s+|um\s+|uma\s+)?",
            r"^estou\s+(?:com|tendo|enfrentando)\s+",
            r"^esta\s+(?:com|tendo|enfrentando)\s+",
            r"^tenho\s+um\s+",
            r"^tenho\s+uma\s+",
            r"^(?:o|a|um|uma)\s+",
        )
        cleaned = title.strip(" .:-")
        for pattern in replacements:
            cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE).strip(" .:-")
        return cleaned

    @staticmethod
    def _normalize_punctuation(title: str) -> str:
        title = re.sub(r"\s+([,.:;!?])", r"\1", title)
        title = re.sub(r"([,.:;!?]){2,}", r"\1", title)
        title = re.sub(r"\s*[-–—]\s*", " - ", title)
        title = re.sub(r"\s+", " ", title)
        return title.strip(" .:-")

    @staticmethod
    def _apply_common_terms(title: str) -> str:
        replacements = {
            r"\bwi[\s-]?fi\b": "Wi-Fi",
            r"\bglpi\b": "GLPI",
            r"\berp\b": "ERP",
            r"\bvpn\b": "VPN",
            r"\bcpf\b": "CPF",
            r"\bnf-e\b": "NF-e",
            r"\boffice\s*365\b": "Office 365",
            r"\bmicrosoft\s*365\b": "Microsoft 365",
        }
        for pattern, replacement in replacements.items():
            title = re.sub(pattern, replacement, title, flags=re.IGNORECASE)
        return title

    @classmethod
    def _limit_title(cls, title: str) -> str:
        words = title.split()
        if len(words) > cls.MAX_TITLE_WORDS:
            title = " ".join(words[: cls.MAX_TITLE_WORDS])
        if len(title) <= cls.MAX_TITLE_CHARS:
            return title.strip(" .:-")

        for separator in (" - ", ": ", ", "):
            cut_at = title.rfind(separator, 0, cls.MAX_TITLE_CHARS + 1)
            if cut_at >= 24:
                return title[:cut_at].strip(" .:-")

        cut_at = title.rfind(" ", 0, cls.MAX_TITLE_CHARS + 1)
        if cut_at >= 24:
            return title[:cut_at].strip(" .:-")
        return title[: cls.MAX_TITLE_CHARS].rstrip(" .:-")

    @staticmethod
    def _ensure_professional_case(title: str) -> str:
        if not title:
            return title
        first = title[0]
        if first.isalpha() and first.islower():
            return first.upper() + title[1:]
        return title

    @staticmethod
    def _is_too_generic(title: str) -> bool:
        normalized = re.sub(r"\s+", " ", title or "").strip().casefold()
        generic_titles = {
            "",
            "problema",
            "erro",
            "falha",
            "solicitacao",
            "chamado",
            "chamado de ti",
            "suporte",
            "ajuda",
            "nao funciona",
            "nao consigo",
        }
        return normalized in generic_titles
