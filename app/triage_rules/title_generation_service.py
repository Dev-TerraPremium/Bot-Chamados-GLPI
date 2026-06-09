import re
import unicodedata


MAX_TITLE_LENGTH = 90

NOISE_PATTERNS = (
    r"^(eu\s+)?estou\s+com\s+(um\s+)?problema\s+(aqui\s+)?(no|na|em|com)\s+",
    r"^(eu\s+)?estou\s+com\s+(um\s+)?problema\s+de\s+",
    r"^(eu\s+)?estou\s+com\s+(um\s+)?problema\s+",
    r"^(eu\s+)?tenho\s+(um\s+)?problema\s+(no|na|em|com)\s+",
    r"^(o|a|meu|minha)\s+",
    r"^preciso\s+(de|do|da|dos|das)\s+",
    r"^solicito\s+(a|o|um|uma)?\s*",
    r"^(a\s+)?compra\s+(de|do|da|dos|das)\s+(um\s+|uma\s+)?",
)

SYMPTOM_REPLACEMENTS = (
    (r"\best[aá]\s+fazendo\s+muito\s+barulho\b", "com barulho excessivo"),
    (r"\bfazendo\s+muito\s+barulho\b", "com barulho excessivo"),
    (r"\bn[aã]o\s+liga\b", "não liga"),
    (r"\bn[aã]o\s+abre\b", "não abre"),
    (r"\bn[aã]o\s+funciona\b", "não funciona"),
    (r"\best[aá]\s+lento\b", "lento"),
    (r"\btravando\b", "travando"),
    (r"\bfalhando\b", "falhando"),
    (r"\bcom\s+erro\b", "com erro"),
)


class TitleGenerationService:
    def generate_title(self, category_name: str, description: str) -> str:
        normalized_description = self._normalize_description(description)
        if not normalized_description:
            return "Chamado de TI"

        title = self._build_functional_title(category_name, normalized_description)
        return self._limit_title(title or normalized_description)

    @classmethod
    def clean_title(cls, title: str, category_name: str = "") -> str:
        normalized_title = cls._normalize_description(title)
        category = cls._normalize_description(category_name)
        if category and normalized_title.casefold().startswith(category.casefold()):
            normalized_title = normalized_title[len(category) :].strip(" .:-")
        if (
            " - " in normalized_title
            and ">" in normalized_title.split(" - ", maxsplit=1)[0]
        ):
            normalized_title = normalized_title.split(" - ", maxsplit=1)[1].strip()
        if ">" in normalized_title:
            normalized_title = normalized_title.split(">")[-1].strip(" .:-")
        return cls._limit_title(normalized_title or "Chamado de TI")

    @classmethod
    def _build_functional_title(cls, category_name: str, description: str) -> str:
        text = cls._remove_noise_prefix(description)
        lowered = cls._strip_accents(text.casefold())

        object_name = cls._object_from_text(lowered, text)
        symptom = cls._symptom_from_text(lowered, text)

        if object_name and symptom:
            return cls._capitalize(f"{object_name} {symptom}")

        category_hint = cls._object_from_category(category_name)
        if category_hint and symptom:
            return cls._capitalize(f"{category_hint} {symptom}")

        return cls._capitalize(text)

    @staticmethod
    def _normalize_description(value: str) -> str:
        value = re.sub(r"\s+", " ", value or "").strip()
        return value.strip(" .!?;:")

    @classmethod
    def _remove_noise_prefix(cls, value: str) -> str:
        cleaned = value.strip()
        for pattern in NOISE_PATTERNS:
            cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE).strip()
        return cleaned or value

    @staticmethod
    def _strip_accents(value: str) -> str:
        normalized = unicodedata.normalize("NFKD", value)
        return "".join(char for char in normalized if not unicodedata.combining(char))

    @classmethod
    def _object_from_text(cls, lowered: str, original: str) -> str:
        known_objects = (
            ("computador", "computador"),
            ("notebook", "notebook"),
            ("ventoinha", "ventoinha"),
            ("impressora", "impressora"),
            ("internet", "internet"),
            ("rede", "rede"),
            ("wifi", "Wi-Fi"),
            ("wi-fi", "Wi-Fi"),
            ("mouse", "mouse"),
            ("teclado", "teclado"),
            ("monitor", "monitor"),
            ("email", "e-mail"),
            ("e-mail", "e-mail"),
            ("outlook", "Outlook"),
            ("teams", "Teams"),
            ("erp", "ERP"),
            ("glpi", "GLPI"),
            ("senha", "senha"),
            ("acesso", "acesso"),
            ("ramal", "ramal"),
            ("telefone", "telefone"),
            ("camera", "câmera"),
            ("cameras", "câmeras"),
            ("cftv", "CFTV"),
        )
        for needle, label in known_objects:
            if re.search(rf"\b{re.escape(needle)}\b", lowered):
                return label

        match = re.search(
            r"\b(no|na|em|com)\s+(.+?)(?:\s+(esta|est[aá]|com|que|quando)\b|$)",
            original,
            re.IGNORECASE,
        )
        if match:
            return match.group(2).strip(" .:-")
        return ""

    @staticmethod
    def _symptom_from_text(lowered: str, original: str) -> str:
        for pattern, replacement in SYMPTOM_REPLACEMENTS:
            if re.search(pattern, lowered, flags=re.IGNORECASE):
                return replacement
        match = re.search(
            r"\b(com|sem)\s+([a-z0-9çãõáéíóúâêôàü\s-]{3,40})",
            original,
            re.IGNORECASE,
        )
        if match:
            return f"{match.group(1).lower()} {match.group(2).strip()}"
        return ""

    @classmethod
    def _object_from_category(cls, category_name: str) -> str:
        category = cls._strip_accents((category_name or "").casefold())
        if "computador" in category:
            return "computador"
        if "impressora" in category:
            return "impressora"
        if "internet" in category or "rede" in category:
            return "rede"
        if "email" in category or "microsoft" in category:
            return "e-mail"
        return ""

    @staticmethod
    def _capitalize(value: str) -> str:
        value = value.strip()
        if not value:
            return value
        return value[0].upper() + value[1:]

    @staticmethod
    def _limit_title(value: str) -> str:
        value = re.sub(r"\s+", " ", value).strip(" .:-")
        if len(value) <= MAX_TITLE_LENGTH:
            return value or "Chamado de TI"
        words = value[: MAX_TITLE_LENGTH + 1].split()
        if len(words) > 1:
            value = " ".join(words[:-1])
        else:
            value = value[:MAX_TITLE_LENGTH]
        return value.strip(" .:-") or "Chamado de TI"
