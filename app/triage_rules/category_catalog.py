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
        ("Estou sem internet.", "A rede esta oscilando.", "Nao acesso a VPN."),
    ),
    CategoryOption(
        2,
        "Computador / Notebook",
        "Descreva brevemente o problema no computador ou notebook.",
        ("Notebook nao liga.", "Computador esta lento.", "Tela esta piscando."),
    ),
    CategoryOption(
        3,
        "Impressora",
        "Descreva brevemente o problema de impressao.",
        ("Nao consigo imprimir.", "Impressora esta atolando papel.", "Fila travada."),
    ),
    CategoryOption(
        4,
        "Sistema / ERP",
        "Descreva brevemente o problema no sistema ou ERP.",
        ("ERP travando.", "Sistema apresenta erro ao salvar.", "Tela nao carrega."),
    ),
    CategoryOption(
        5,
        "E-mail / Microsoft 365",
        "Descreva brevemente o problema de e-mail ou Microsoft 365.",
        ("E-mail nao abre.", "Outlook nao sincroniza.", "Teams nao entra."),
    ),
    CategoryOption(
        6,
        "Acesso / Senha",
        "Descreva brevemente o problema ou solicitacao de acesso.",
        (
            "Esqueci minha senha do ERP.",
            "Meu usuario do Windows esta bloqueado.",
            "Preciso de acesso a pasta Financeiro.",
            "Preciso alterar a permissao de um colaborador.",
            "MFA nao esta funcionando.",
        ),
    ),
    CategoryOption(
        7,
        "Telefonia",
        "Descreva brevemente o problema de telefonia.",
        ("Ramal sem linha.", "Telefone mudo.", "Nao consigo transferir ligacao."),
    ),
    CategoryOption(
        8,
        "GLPI",
        "Descreva brevemente o problema relacionado ao GLPI.",
        ("GLPI nao abre.", "Nao consigo consultar chamado.", "Erro ao fechar chamado."),
    ),
    CategoryOption(
        9,
        "Solicitacao de equipamento",
        "Descreva brevemente o equipamento solicitado.",
        ("Preciso de mouse.", "Solicito um monitor.", "Novo colaborador precisa de kit."),
    ),
    CategoryOption(
        10,
        "Cameras / CFTV",
        "Descreva brevemente o problema de cameras ou CFTV.",
        ("Camera sem imagem.", "DVR offline.", "Imagem travando."),
    ),
    CategoryOption(
        11,
        "Ubiquiti / Wi-Fi",
        "Descreva brevemente o problema de Wi-Fi ou Ubiquiti.",
        ("Wi-Fi caindo.", "Access point offline.", "Sinal fraco no deposito."),
    ),
    CategoryOption(
        12,
        "Outro",
        "Descreva brevemente o problema ou solicitacao.",
        ("Tenho uma solicitacao diferente.",),
    ),
)


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
    lines = ["Escolha uma categoria:"]
    lines.extend(f"{category.id}. {category.name}" for category in CATEGORY_OPTIONS)
    return "\n".join(lines)


def render_description_prompt(category: CategoryOption) -> str:
    examples = "\n".join(f"- {example}" for example in category.examples)
    return (
        f"Categoria selecionada:\n{category.name}\n\n"
        f"{category.description_hint}\n\n"
        f"Exemplos:\n{examples}\n\n"
        "Digite em poucas palavras o que aconteceu ou o que voce precisa:"
    )

