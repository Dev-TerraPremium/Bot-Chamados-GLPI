from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CategoryOption:
    id: int
    name: str
    description_hint: str
    examples: tuple[str, ...]


CATEGORY_OPTIONS: tuple[CategoryOption, ...] = (
    CategoryOption(
        1,
        "Internet / Rede",
        "Descreva brevemente o problema de rede ou internet.",
        ("Estou sem internet.", "A rede está oscilando.", "Não acesso a VPN."),
    ),
    CategoryOption(
        2,
        "Computador / Notebook",
        "Descreva brevemente o problema no computador ou notebook.",
        ("Notebook não liga.", "Computador está lento.", "Tela está piscando."),
    ),
    CategoryOption(
        3,
        "Impressora",
        "Descreva brevemente o problema de impressão.",
        ("Não consigo imprimir.", "Impressora está atolando papel.", "Fila travada."),
    ),
    CategoryOption(
        4,
        "Sistema / ERP",
        "Descreva brevemente o problema no sistema ou ERP.",
        ("ERP travando.", "Sistema apresenta erro ao salvar.", "Tela não carrega."),
    ),
    CategoryOption(
        5,
        "E-mail / Microsoft 365",
        "Descreva brevemente o problema de e-mail ou Microsoft 365.",
        ("E-mail não abre.", "Outlook não sincroniza.", "Teams não entra."),
    ),
    CategoryOption(
        6,
        "Acesso / Senha",
        "Descreva brevemente o problema ou solicitação de acesso.",
        (
            "Esqueci minha senha do ERP.",
            "Meu usuário do Windows está bloqueado.",
            "Preciso de acesso à pasta Financeiro.",
            "Preciso alterar a permissão de um colaborador.",
            "MFA não está funcionando.",
        ),
    ),
    CategoryOption(
        7,
        "Telefonia",
        "Descreva brevemente o problema de telefonia.",
        ("Ramal sem linha.", "Telefone mudo.", "Não consigo transferir ligação."),
    ),
    CategoryOption(
        8,
        "GLPI",
        "Descreva brevemente o problema relacionado ao GLPI.",
        ("GLPI não abre.", "Não consigo consultar chamado.", "Erro ao fechar chamado."),
    ),
    CategoryOption(
        9,
        "Solicitação de equipamento",
        "Descreva brevemente o equipamento solicitado.",
        ("Preciso de mouse.", "Solicito um monitor.", "Novo colaborador precisa de kit."),
    ),
    CategoryOption(
        10,
        "Câmeras / CFTV",
        "Descreva brevemente o problema de câmeras ou CFTV.",
        ("Câmera sem imagem.", "DVR offline.", "Imagem travando."),
    ),
    CategoryOption(
        11,
        "Ubiquiti / Wi-Fi",
        "Descreva brevemente o problema de Wi-Fi ou Ubiquiti.",
        ("Wi-Fi caindo.", "Access point offline.", "Sinal fraco no depósito."),
    ),
    CategoryOption(
        12,
        "Outro",
        "Descreva brevemente o problema ou solicitação.",
        ("Tenho uma solicitação diferente.",),
    ),
)

CATEGORY_ICONS_BY_ID = {
    1: "🌐",
    2: "💻",
    3: "🖨️",
    4: "🧩",
    5: "📧",
    6: "🔐",
    7: "☎️",
    8: "🎫",
    9: "🚜",
    10: "📹",
    11: "📡",
    12: "🧰",
}


def get_category_by_id(category_id: int) -> CategoryOption | None:
    return next(
        (category for category in CATEGORY_OPTIONS if category.id == category_id),
        None,
    )


def get_category_by_name(category_name: str) -> CategoryOption | None:
    normalized_name = category_name.strip().casefold()
    return next(
        (
            category
            for category in CATEGORY_OPTIONS
            if category.name.casefold() == normalized_name
        ),
        None,
    )


def render_category_menu() -> str:
    return (
        "📚 **Catálogo de Serviços**\n\n"
        "Selecione a categoria que melhor descreve sua necessidade:\n"
        "1️⃣ **Internet e Conectividade**\n"
        "2️⃣ **Computador ou Notebook**\n"
        "3️⃣ **Sistemas e ERP**\n"
        "4️⃣ **Acessos e Senhas**\n"
        "5️⃣ **Impressoras e Periféricos**\n"
        "6️⃣ **E-mail e Microsoft 365**\n"
        "7️⃣ **Outros Assuntos**\n"
        "8️⃣ **🔍 Pesquisar por nome**\n"
        "9️⃣ **⬅️ Voltar**"
    )


def render_description_prompt(category: CategoryOption) -> str:
    examples = "\n".join(f"- {example}" for example in category.examples)
    return (
        f"✅ **Categoria selecionada:**\n"
        f"{CATEGORY_ICONS_BY_ID[category.id]} **{category.name}**\n\n"
        f"{category.description_hint}\n\n"
        f"**Exemplos:**\n{examples}\n\n"
        "Digite em poucas palavras o que aconteceu ou o que você precisa:"
    )


def _keycap(number: int) -> str:
    return {
        1: "1️⃣",
        2: "2️⃣",
        3: "3️⃣",
        4: "4️⃣",
        5: "5️⃣",
        6: "6️⃣",
        7: "7️⃣",
        8: "8️⃣",
        9: "9️⃣",
        10: "🔟",
        11: "1️⃣1️⃣",
        12: "1️⃣2️⃣",
    }[number]
