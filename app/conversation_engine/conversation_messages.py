from app.authentication_and_identity.authenticated_user_model import AuthenticatedUser


def build_main_menu(user: AuthenticatedUser, opening_only: bool = False) -> str:
    if opening_only:
        return (
            f"👋 Olá, **{user.first_name}**!\n"
            f"Você está conectado como **{user.login}** no Suporte TI — Terra Premium.\n\n"
            "Como posso ser útil agora?\n\n"
            "Digite o número da opção desejada:\n"
            "1️⃣ **Abrir um novo chamado**\n"
            "2️⃣ **Encerrar atendimento**"
        )
    return (
        f"👋 Olá, **{user.first_name}**!\n"
        f"Você está conectado como **{user.login}** no Suporte TI — Terra Premium.\n\n"
        "Como posso ser útil agora?\n\n"
        "Digite o número da opção desejada:\n"
        "1️⃣ **Abrir um novo chamado**\n"
        "2️⃣ **Consultar meus chamados**\n"
        "3️⃣ **Complementar chamado existente**\n"
        "4️⃣ **Encerrar atendimento**"
    )


def build_open_ticket_prompt() -> str:
    return (
        "📝 **Relato da Solicitação**\n\n"
        "Por favor, descreva abaixo o que está acontecendo ou o que você precisa.\n\n"
        "💡 **Dica:** Não se preocupe com a organização agora. Se faltar algum detalhe, eu farei perguntas rápidas para me ajudar a entender melhor.\n\n"
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
    return (
        "🔍 **Refinando Informações**\n\n"
        "Para que o TI resolva mais rápido, preciso de um detalhe adicional:\n\n"
        f"📋 **Passo {question_number} de {max_questions}**\n"
        f"{question}\n\n"
        "👉 Responda de forma breve. Se não souber a resposta, digite **pular**."
    )


def build_category_assignment_message(
    organized_text: str,
    category_id: int,
    category_name: str,
) -> str:
    return (
        "🏷️ **Sugestão de Classificação**\n\n"
        "Com base no seu relato, identifiquei a seguinte categoria:\n"
        f"📂 **{category_name}**\n\n"
        "Abaixo, veja como organizei seu texto para o técnico:\n"
        f'"{organized_text}"\n\n'
        "Como deseja prosseguir?\n\n"
        "1️⃣ **Sim, está correto**\n"
        "2️⃣ **Alterar categoria manualmente**\n"
        "3️⃣ **Reescrever minha descrição**\n"
        "4️⃣ **Cancelar abertura**"
    )


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


def build_description_review_message(organized_text: str) -> str:
    return (
        "👁️ **Revisão do Chamado**\n\n"
        "Confira como sua solicitação será enviada ao técnico:\n\n"
        f'📝 "{organized_text}"\n\n'
        "O texto reflete bem o seu problema?\n\n"
        "1️⃣ **Sim, continuar**\n"
        "2️⃣ **Não, quero ajustar o texto**\n"
        "3️⃣ **Usar meu texto original**\n"
        "4️⃣ **Cancelar**"
    )


def build_location_prompt() -> str:
    return (
        "🏢 **Sua Localização**\n\n"
        "Para que o técnico saiba onde atuar, informe sua Unidade e Setor.\n\n"
        "📍 **Exemplo:** Matriz - Financeiro\n\n"
        "Digite sua localização abaixo:"
    )


def build_evidence_question() -> str:
    return (
        "📸 **Fotos e Evidências**\n\n"
        "Você gostaria de enviar fotos, prints de erro ou documentos para ajudar na análise?\n\n"
        "1️⃣ **Sim, enviar anexos**\n"
        "2️⃣ **Não, prosseguir sem anexos**"
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
