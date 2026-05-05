from app.authentication_and_identity.authenticated_user_model import AuthenticatedUser


def build_main_menu(user: AuthenticatedUser) -> str:
    return (
        f"👋 Olá, **{user.first_name}**.\n"
        f"Você está autenticado como **{user.login}**.\n\n"
        "🌾 **Terra Premium | Assistente de Chamados TI**\n"
        "Como posso te ajudar hoje?\n\n"
        "1. 🆕 **Abrir novo chamado**\n"
        "2. 🔎 **Consultar meus chamados**\n"
        "3. 📝 **Complementar chamado existente**\n"
        "4. 🚪 **Sair**"
    )


def build_opening_mode_menu() -> str:
    return (
        "🧭 **Escolha o tipo de abertura:**\n\n"
        "1. ⚡ **Chamado rápido**\n"
        "2. 📋 **Chamado detalhado**\n"
        "3. ↩️ **Voltar ao menu**"
    )


def build_query_menu() -> str:
    return (
        "🔎 **Consultar chamados:**\n\n"
        "1. 🟢 **Meus chamados abertos**\n"
        "2. 🛠️ **Meus chamados em atendimento**\n"
        "3. 🕘 **Meus últimos chamados**\n"
        "4. 🔢 **Consultar pelo número do chamado**\n"
        "5. ↩️ **Voltar ao menu**"
    )


def build_invalid_option_message() -> str:
    return "⚠️ Não entendi a opção. Responda apenas com o **número** de uma das opções."


def build_description_review_message(organized_text: str) -> str:
    return (
        "🤖 **Organizei sua solicitação assim:**\n\n"
        f"{organized_text}\n\n"
        "Está correto?\n\n"
        "1. ✅ **Sim, continuar**\n"
        "2. ✍️ **Não, quero reescrever**\n"
        "3. 📌 **Manter exatamente como digitei**\n"
        "4. ❌ **Cancelar chamado**"
    )


def build_location_prompt() -> str:
    return (
        "📍 **Informe a localidade ou setor relacionado ao chamado.**\n\n"
        "Exemplos:\n"
        "- RH - Rondonópolis\n"
        "- Financeiro - Matriz\n"
        "- Oficina - Primavera\n"
        "- Administrativo - Roo"
    )


def build_evidence_question() -> str:
    return (
        "📎 **Você possui erro, print ou informação adicional?**\n\n"
        "1. ✅ **Sim, vou descrever**\n"
        "2. ➖ **Não**"
    )


def build_complement_review_message(rewritten_text: str) -> str:
    return (
        "🤖 **Organizei seu complemento assim:**\n\n"
        f"{rewritten_text}\n\n"
        "Está correto?\n\n"
        "1. ✅ **Sim, adicionar acompanhamento**\n"
        "2. ✍️ **Não, quero reescrever**\n"
        "3. 📌 **Manter exatamente como digitei**\n"
        "4. ❌ **Cancelar**"
    )
