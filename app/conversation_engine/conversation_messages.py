from app.authentication_and_identity.authenticated_user_model import AuthenticatedUser


def build_main_menu(user: AuthenticatedUser, opening_only: bool = False) -> str:
    if opening_only:
        return (
            f"Ola, **{user.first_name}**.\n"
            f"Voce esta autenticado como **{user.login}**.\n\n"
            "Terra Premium | Assistente de Chamados TI\n"
            "Como posso te ajudar hoje?\n\n"
            "1. **Abrir chamado**\n"
            "2. **Sair**"
        )
    return (
        f"👋 Olá, **{user.first_name}**.\n"
        f"Você está autenticado como **{user.login}**.\n\n"
        "🌾 **Terra Premium | Assistente de Chamados TI**\n"
        "Como posso te ajudar hoje?\n\n"
        "1. 🆕 **Abrir chamado**\n"
        "2. 🔎 **Consultar meus chamados**\n"
        "3. 📝 **Complementar chamado existente**\n"
        "4. 🚪 **Sair**"
    )


def build_open_ticket_prompt() -> str:
    return (
        "🆕 **Vamos abrir seu chamado.**\n\n"
        "📝 **Descreva em poucas palavras** o que aconteceu ou o que você precisa.\n"
        "💬 **Se faltar detalhe**, eu posso fazer algumas perguntas rápidas antes de organizar o texto.\n"
        "✨ Depois vou **sugerir a categoria automaticamente**.\n\n"
        "✅ Você poderá **confirmar a categoria sugerida** ou 📚 **escolher outra manualmente**."
    )

def build_ticket_type_prompt() -> str:
    return (
        "🤔 **Você está com um problema ou precisa solicitar algo novo?**\n\n"
        "1. 💥 **Estou com um problema** (Incidente / Algo parou)\n"
        "2. ➕ **Quero solicitar algo** (Requisição / Novo acesso / Novo equipamento)"
    )

def build_description_clarification_message(
    question: str,
    question_number: int,
    max_questions: int,
) -> str:
    return (
        "🤖 **Vou detalhar um pouco melhor antes de abrir o chamado.**\n\n"
        f"Pergunta {question_number} de até {max_questions}:\n"
        f"{question}\n\n"
        "Responda em uma frase curta. Se não souber, diga **não sei** ou **pular**."
    )


def build_category_assignment_message(
    organized_text: str,
    category_id: int,
    category_name: str,
) -> str:
    return (
        "🤖 **Organizei sua solicitação e encontrei uma categoria provável:**\n\n"
        f"📝 **Descrição organizada:** {organized_text}\n\n"
        f"📚 **Categoria sugerida:** {category_id}. **{category_name}**\n\n"
        "Como deseja seguir?\n\n"
        "1. ✅ **Usar essa categoria**\n"
        "2. 📚 **Escolher categoria manualmente**\n"
        "3. 🧰 **Manter como Outro**\n"
        "4. ✍️ **Reescrever descrição**\n"
        "5. ❌ **Cancelar chamado**"
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
    return (
        "⚠️ Não entendi a opção. Responda apenas com o **número** "
        "de uma das opções exibidas."
    )


def build_description_review_message(organized_text: str) -> str:
    return (
        "🤖 **Descrição final do chamado:**\n\n"
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
        "💡 **Exemplos:**\n"
        "🏢 **RH** - Rondonópolis\n"
        "💰 **Financeiro** - Matriz\n"
        "🛠️ **Oficina** - Primavera\n"
        "📋 **Administrativo** - Roo"
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
