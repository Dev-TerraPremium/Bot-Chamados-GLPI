from dataclasses import dataclass
import re

from app.triage_rules.category_catalog import get_category_by_id


@dataclass(frozen=True, slots=True)
class CategoryMatch:
    category_id: int
    category_name: str
    confidence: float
    matched_keyword: str


class CategoryMatchingService:
    KEYWORD_RULES: tuple[tuple[int, tuple[str, ...]], ...] = (
        (11, ("wifi", "wi-fi", "ubiquiti", "access point", "ap caindo", "sinal fraco")),
        (3, ("imprimir", "impressora", "impressao", "fila de impressao", "toner")),
        (4, ("erp", "sistema", "travando", "erro ao salvar", "tela nao carrega")),
        (1, ("sem internet", "internet", "rede", "vpn", "cabo de rede")),
        (5, ("email", "e-mail", "outlook", "microsoft 365", "office 365")),
        (6, ("senha", "bloqueada", "bloqueado", "acesso", "permissao", "mfa")),
        (10, ("camera", "cameras", "cftv", "dvr", "sem imagem")),
        (7, ("telefone", "telefonia", "ramal", "ligacao")),
        (8, ("glpi", "chamado")),
        (9, ("equipamento", "mouse", "teclado", "monitor", "notebook novo")),
        (2, ("computador", "notebook", "lento", "nao liga", "tela")),
    )

    def find_best_match(self, text: str) -> CategoryMatch:
        normalized_text = self._normalize(text)
        for category_id, keywords in self.KEYWORD_RULES:
            for keyword in keywords:
                if keyword in normalized_text:
                    category = get_category_by_id(category_id)
                    if category is None:
                        continue
                    return CategoryMatch(
                        category_id=category.id,
                        category_name=category.name,
                        confidence=0.8,
                        matched_keyword=keyword,
                    )

        fallback = get_category_by_id(12)
        return CategoryMatch(
            category_id=fallback.id,
            category_name=fallback.name,
            confidence=0.0,
            matched_keyword="",
        )

    @staticmethod
    def _normalize(text: str) -> str:
        text = text.casefold()
        text = re.sub(r"\s+", " ", text)
        replacements = {
            "á": "a",
            "à": "a",
            "ã": "a",
            "â": "a",
            "é": "e",
            "ê": "e",
            "í": "i",
            "ó": "o",
            "ô": "o",
            "õ": "o",
            "ú": "u",
            "ç": "c",
        }
        for source, target in replacements.items():
            text = text.replace(source, target)
        return text.strip()

