from app.authentication_and_identity.authenticated_user_model import AuthenticatedUser


def build_main_menu(user: AuthenticatedUser, opening_only: bool = False) -> str:
    if opening_only:
        return (
            f"👋 Olá, **{user.first_name}**!\n"
            f"Você está conectado como **{user.login}** no Suporte TI - Terra Premium.\n\n"
            "Como posso ajudar agora?\n\n"
            "Digite o número da opção desejada:\n"
            "1️⃣ **Abrir um novo chamado**\n"
            "2️⃣ **Encerrar atendimento**"
        )
    return (
        f"👋 Olá, **{user.first_name}**!\n"
        f"Você está conectado como **{user.login}** no Suporte TI - Terra Premium.\n\n"
        "Como posso ajudar agora?\n\n"
        "Digite o número da opção desejada:\n"
        "1️⃣ **Abrir um novo chamado**\n"
        "2️⃣ **Consultar meus chamados**\n"
        "3️⃣ **Complementar chamado existente**\n"
        "4️⃣ **Encerrar atendimento**"
    )


def build_open_ticket_prompt() -> str:
    return (
        "📝 **Relato da Solicitação**\n\n"
        "Descreva o que está acontecendo ou o que você precisa.\n\n"
        "Se faltar algum detalhe, eu vou te perguntar em seguida.\n\n"
        "Pode digitar sua descrição agora:"
    )


def build_ticket_type_prompt() -> str:
    return (
        "🛠️ **Classificação da Demanda**\n\n"
        "Para direcionar sua solicitação ao técnico correto, selecione o tipo de atendimento:\n\n"
        "1️⃣ **Estou com um problema** (Algo parou de funcionar ou está com erro)\n"
        "2️⃣ **Preciso de algo novo** (Acessos, equipamentos ou novas instalações)\n\n"
        "Digite o número correspondente:"
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
        "📂 **Meus Chamados**\n\n"
        "Como você deseja localizar seus tickets?\n\n"
        "1️⃣ 🟢 **Chamados em aberto**\n"
        "2️⃣ 🔵 **Chamados em atendimento**\n"
        "3️⃣ 🕒 **Ver histórico recente**\n"
        "4️⃣ 🔢 **Buscar por número (ID)**\n"
        "5️⃣ ⬅️ **Voltar ao início**"
    )


def build_invalid_option_message() -> str:
    return (
        "⚠️ Não entendi a opção. Responda apenas com o **número** "
        "de uma das opções exibidas."
    )


def build_description_review_message(
    organized_text: str,
    category_name: str | None = None,
) -> str:
    category_block = ""
    if category_name:
        category_block = (
            "Categoria definida para o chamado:\n"
            f"📂 **{category_name}**\n\n"
        )
    return (
        "👁️ **Revisão do Chamado**\n\n"
        f"{category_block}"
        "Confira como sua solicitação será enviada ao técnico:\n\n"
        f'📝 "{organized_text}"\n\n'
        "O texto reflete bem o seu problema?\n\n"
        "1️⃣ **Sim, continuar**\n"
        "2️⃣ **Não, quero ajustar o texto**\n"
        "3️⃣ **Usar meu texto original**\n"
        "4️⃣ **Cancelar**"
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
