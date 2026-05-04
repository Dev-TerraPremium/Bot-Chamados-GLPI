from app.authentication_and_identity.authenticated_user_model import AuthenticatedUser


def build_main_menu(user: AuthenticatedUser) -> str:
    return (
        f"Ola, {user.first_name}.\n"
        f"Voce esta autenticado como {user.login}.\n\n"
        "O que deseja fazer?\n\n"
        "1. Abrir novo chamado\n"
        "2. Consultar meus chamados\n"
        "3. Complementar chamado existente\n"
        "4. Sair"
    )


def build_opening_mode_menu() -> str:
    return (
        "Escolha o tipo de abertura:\n\n"
        "1. Chamado rapido\n"
        "2. Chamado detalhado\n"
        "3. Voltar"
    )


def build_query_menu() -> str:
    return (
        "Consultar chamados:\n\n"
        "1. Meus chamados abertos\n"
        "2. Meus chamados em atendimento\n"
        "3. Meus ultimos chamados\n"
        "4. Consultar pelo numero do chamado\n"
        "5. Voltar"
    )


def build_invalid_option_message() -> str:
    return "Nao entendi a opcao. Responda apenas com o numero de uma das opcoes."


def build_description_review_message(organized_text: str) -> str:
    return (
        "Organizei sua solicitacao assim:\n\n"
        f"{organized_text}\n\n"
        "Esta correto?\n\n"
        "1. Sim, continuar\n"
        "2. Nao, quero reescrever\n"
        "3. Manter exatamente como digitei\n"
        "4. Cancelar chamado"
    )


def build_location_prompt() -> str:
    return (
        "Informe a localidade ou setor relacionado ao chamado.\n\n"
        "Exemplos:\n"
        "- RH - Rondonopolis\n"
        "- Financeiro - Matriz\n"
        "- Oficina - Primavera\n"
        "- Administrativo - Roo"
    )


def build_evidence_question() -> str:
    return (
        "Voce possui erro, print ou informacao adicional?\n\n"
        "1. Sim, vou descrever\n"
        "2. Nao"
    )


def build_complement_review_message(rewritten_text: str) -> str:
    return (
        "Organizei seu complemento assim:\n\n"
        f"{rewritten_text}\n\n"
        "Esta correto?\n\n"
        "1. Sim, adicionar acompanhamento\n"
        "2. Nao, quero reescrever\n"
        "3. Manter exatamente como digitei\n"
        "4. Cancelar"
    )

