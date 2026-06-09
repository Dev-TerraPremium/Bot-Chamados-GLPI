from app.authentication_and_identity.authenticated_user_model import AuthenticatedUser


def build_main_menu(user: AuthenticatedUser, opening_only: bool = False) -> str:
    if opening_only:
        return (
            f"👋 Olá, **{user.first_name}**!\n"
            f"Você entrou como **{user.login}** no Suporte TI - Terra Premium.\n\n"
            "O que você quer fazer?\n\n"
            "Digite o número:\n"
            "1️⃣ **Abrir chamado**\n"
            "2️⃣ **Encerrar atendimento**"
        )
    return (
        f"👋 Olá, **{user.first_name}**!\n"
        f"Você entrou como **{user.login}** no Suporte TI - Terra Premium.\n\n"
        "O que você quer fazer?\n\n"
        "Digite o número:\n"
        "1️⃣ **Abrir chamado**\n"
        "2️⃣ **Consultar chamados**\n"
        "3️⃣ **Complementar chamado**\n"
        "4️⃣ **Encerrar atendimento**"
    )


def build_open_ticket_prompt() -> str:
    return (
        "Conte o que aconteceu ou o que você precisa, Se faltar alguma informação, "
        "eu peço depois.\n\n"
        "Digite de maneira completa sua mensagem, descreva o máximo de detalhes:"
    )


def build_ticket_type_prompt() -> str:
    return (
        "Escolha o tipo da sua solicitação:\n\n"
        "1️⃣ **Estou com um problema** (algo parou de funcionar ou está com erro)\n"
        "2️⃣ **Preciso de algo novo** (acesso, equipamento ou instalação)\n\n"
        "Digite o número:"
    )


def build_description_clarification_message(
    question: str,
    question_number: int,
    max_questions: int,
) -> str:
    del question_number
    del max_questions
    return question.strip()


def build_query_menu() -> str:
    return (
        "Veja seus chamados:\n\n"
        "1️⃣ 🟢 **Em aberto**\n"
        "2️⃣ 🔵 **Em atendimento**\n"
        "3️⃣ 🕒 **Histórico recente**\n"
        "4️⃣ 🔢 **Buscar por número**\n"
        "5️⃣ ⬅️ **Voltar**"
    )


def build_invalid_option_message() -> str:
    return (
        "⚠️ Opção inválida. Responda só com o número de uma das opções."
    )


def build_location_prompt(
    retry: bool = False,
    options: list[dict] | None = None,
) -> str:
    if options:
        rendered_options = "\n".join(
            f"{index}\ufe0f\u20e3 {option['display_name']}"
            for index, option in enumerate(options, start=1)
        )
        prefix = (
            "Não consegui identificar essa localidade.\n\n"
            if retry
            else ""
        )
        return (
            "🏢 **Localidade do Chamado**\n\n"
            f"{prefix}"
            "Digite apenas o número da localidade:\n"
            f"{rendered_options}"
        )
    if retry:
        return (
            "🏢 **Localidade do Chamado**\n\n"
            "Não consegui localizar essa unidade no GLPI.\n\n"
            "Informe novamente apenas a localidade que deve constar no chamado.\n\n"
            "📍 **Exemplos:** Matriz, Rondonópolis\n\n"
            "Digite a localidade abaixo:"
        )
    return (
        "🏢 **Localidade do Chamado**\n\n"
        "Informe a localidade que deve constar no chamado.\n\n"
        "📍 **Exemplos:** Matriz, Rondonópolis\n\n"
        "Digite a localidade abaixo:"
    )


def build_evidence_question() -> str:
    return (
        "📸 **Fotos e Evidências**\n\n"
        "Você quer enviar fotos, prints ou documentos para ajudar na análise?\n\n"
        "1️⃣ **Sim, enviar anexos**\n"
        "2️⃣ **Não, seguir sem anexos**"
    )


def build_complement_review_message(rewritten_text: str) -> str:
    return (
        "📝 **Novo Acompanhamento**\n\n"
        "Veja como sua atualização será registrada no chamado:\n\n"
        f'💬 "{rewritten_text}"\n\n'
        "Confirmar envio?\n\n"
        "1️⃣ **Sim, adicionar ao chamado**\n"
        "2️⃣ **Não, ajustar o texto**\n"
        "3️⃣ **Cancelar**"
    )
