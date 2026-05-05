import re


class SuspiciousInputDetector:
    SUSPICIOUS_PATTERNS: tuple[re.Pattern[str], ...] = (
        re.compile(r"\bselect\b", re.IGNORECASE),
        re.compile(r"\bdrop\b", re.IGNORECASE),
        re.compile(r"\bdelete\b", re.IGNORECASE),
        re.compile(r"\binsert\b", re.IGNORECASE),
        re.compile(r"\bupdate\b", re.IGNORECASE),
        re.compile(r"\btruncate\b", re.IGNORECASE),
        re.compile(r"\bexec\b", re.IGNORECASE),
        re.compile(r"<\s*script", re.IGNORECASE),
        re.compile(r"\bpowershell\b", re.IGNORECASE),
        re.compile(r"\bcmd\.exe\b", re.IGNORECASE),
        re.compile(r"\bbash\b", re.IGNORECASE),
        re.compile(r"\bsudo\b", re.IGNORECASE),
        re.compile(r"ignore\s+(as\s+)?instru[cç][oõ]es?", re.IGNORECASE),
        re.compile(r"prompt\s+injection", re.IGNORECASE),
        re.compile(r"listar\s+todos\s+os\s+chamados", re.IGNORECASE),
        re.compile(r"chamados\s+de\s+outro\s+usu[aá]rio", re.IGNORECASE),
        re.compile(r"outro\s+usu[aá]rio", re.IGNORECASE),
        re.compile(r"\badmin\b", re.IGNORECASE),
    )

    def is_suspicious(self, text: str) -> bool:
        return any(pattern.search(text) for pattern in self.SUSPICIOUS_PATTERNS)
