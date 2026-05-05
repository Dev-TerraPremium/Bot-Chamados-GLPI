import logging
from uuid import uuid4

from app.application_config.settings import AppSettings, load_settings
from app.authentication_and_identity.simulated_auth_service import SimulatedAuthService
from app.conversation_engine.conversation_context import ConversationContext
from app.conversation_engine.conversation_input_parser import ConversationInputParser
from app.conversation_engine.conversation_messages import (
    build_complement_review_message,
    build_description_review_message,
    build_evidence_question,
    build_invalid_option_message,
    build_location_prompt,
    build_main_menu,
    build_opening_mode_menu,
    build_query_menu,
)
from app.conversation_engine.conversation_state_machine import ConversationStateMachine
from app.conversation_engine.conversation_states import ConversationState
from app.glpi_integration_reserved.glpi_mock_client import GLPIMockClient
from app.glpi_integration_reserved.glpi_ticket_payload_builder import (
    GLPITicketPayloadBuilder,
)
from app.local_light_ai.description_organization_models import (
    DescriptionOrganizationResult,
    LocalGenerativeAIUnavailableError,
)
from app.local_light_ai.generative_description_organizer import (
    GenerativeDescriptionOrganizer,
    build_generative_description_organizer,
)
from app.security_and_abuse_protection.input_sanitizer import InputSanitizer
from app.security_and_abuse_protection.message_size_limiter import MessageSizeLimiter
from app.security_and_abuse_protection.simple_rate_limiter import SimpleRateLimiter
from app.security_and_abuse_protection.suspicious_input_detector import (
    SuspiciousInputDetector,
)
from app.security_and_abuse_protection.user_scope_guard import UserScopeGuard
from app.shared_kernel.constants import DEFAULT_CHANNEL, SECURITY_BLOCK_MESSAGE
from app.shared_kernel.result_types import ConversationTurnResult
from app.simulated_persistence.in_memory_conversation_store import (
    InMemoryConversationStore,
)
from app.simulated_persistence.in_memory_ticket_store import InMemoryTicketStore
from app.ticket_domain.ticket_enums import TicketOpeningMode, TicketStatus
from app.ticket_domain.ticket_factory import TicketFactory
from app.ticket_domain.ticket_summary_builder import TicketSummaryBuilder
from app.triage_rules.category_catalog import (
    get_category_by_id,
    render_category_menu,
    render_description_prompt,
)
from app.triage_rules.category_matching_service import CategoryMatchingService
from app.triage_rules.impact_catalog import get_impact_by_id, render_impact_menu
from app.triage_rules.severity_mapping_service import SeverityMappingService
from app.triage_rules.title_generation_service import TitleGenerationService


logger = logging.getLogger(__name__)


class ConversationFlowController:
    def __init__(
        self,
        settings: AppSettings | None = None,
        auth_service: SimulatedAuthService | None = None,
        conversation_store: InMemoryConversationStore | None = None,
        ticket_store: InMemoryTicketStore | None = None,
        glpi_client: GLPIMockClient | None = None,
        description_organizer: GenerativeDescriptionOrganizer | None = None,
    ) -> None:
        self.settings = settings or load_settings()
        self.auth_service = auth_service or SimulatedAuthService()
        self.conversation_store = conversation_store or InMemoryConversationStore()
        self.ticket_store = ticket_store or InMemoryTicketStore()
        self.glpi_client = glpi_client or GLPIMockClient(self.ticket_store)
        self.parser = ConversationInputParser()
        self.state_machine = ConversationStateMachine()
        self.input_sanitizer = InputSanitizer()
        self.size_limiter = MessageSizeLimiter(self.settings.max_message_length)
        self.rate_limiter = SimpleRateLimiter(
            self.settings.rate_limit_messages_per_minute
        )
        self.suspicious_detector = SuspiciousInputDetector()
        self.user_scope_guard = UserScopeGuard()
        self.category_matching_service = CategoryMatchingService()
        self.severity_mapping_service = SeverityMappingService()
        self.title_generation_service = TitleGenerationService()
        self.ticket_summary_builder = TicketSummaryBuilder()
        self.ticket_factory = TicketFactory()
        self.glpi_payload_builder = GLPITicketPayloadBuilder()
        self.description_organizer = (
            description_organizer
            or build_generative_description_organizer(self.settings)
        )

    def process_message(
        self,
        session_id: str,
        message: str,
        channel: str = DEFAULT_CHANNEL,
    ) -> ConversationTurnResult:
        normalized_session_id = session_id.strip() or str(uuid4())
        context = self._get_or_create_context(normalized_session_id, channel)

        if self.parser.is_start_message(message):
            return self._result(context, build_main_menu(context.user))

        if self.parser.is_reset_command(message):
            context.move_to_main_menu()
            self.rate_limiter.reset(context.session_id)
            self.conversation_store.save(context)
            return self._result(
                context,
                "🔄 **Conversa reiniciada com segurança.**\n\n" + build_main_menu(context.user),
            )

        if not self.rate_limiter.allow_message(context.session_id):
            return self._result(
                context,
                "Muitas mensagens em pouco tempo. Aguarde um instante e tente novamente.",
            )

        if self.suspicious_detector.is_suspicious(message):
            logger.warning(
                "suspicious_input_blocked",
                extra={"session_id": context.session_id, "state": context.state.value},
            )
            return self._result(context, SECURITY_BLOCK_MESSAGE)

        try:
            self.size_limiter.ensure_allowed(message)
        except ValueError:
            return self._result(
                context,
                "✂️ Sua mensagem está muito longa. Envie uma descrição mais curta, por favor.",
            )

        sanitized_message = self.input_sanitizer.sanitize(message)
        if not sanitized_message:
            return self._result(
                context,
                "Envie uma mensagem com texto para continuar.",
            )

        handler = self._get_handler(context.state)
        result = handler(context, sanitized_message)
        self.conversation_store.save(context)
        logger.info(
            "conversation_turn_processed",
            extra={"session_id": context.session_id, "state": context.state.value},
        )
        return result

    def reset_conversation(
        self, session_id: str, channel: str = DEFAULT_CHANNEL
    ) -> ConversationTurnResult:
        normalized_session_id = session_id.strip() or str(uuid4())
        self.conversation_store.delete(normalized_session_id)
        self.rate_limiter.reset(normalized_session_id)
        context = self._get_or_create_context(normalized_session_id, channel)
        return self._result(
            context,
            "🔄 **Conversa reiniciada com segurança.**\n\n" + build_main_menu(context.user),
        )

    def debug_session(self, session_id: str) -> dict | None:
        return self.conversation_store.debug_context(session_id)

    def _get_or_create_context(
        self, session_id: str, channel: str
    ) -> ConversationContext:
        context = self.conversation_store.get(session_id)
        if context is not None:
            return context

        user = self.auth_service.authenticate_session(session_id, channel)
        context = ConversationContext(
            session_id=session_id,
            channel=channel,
            user=user,
            state=ConversationState.MAIN_MENU,
        )
        self.conversation_store.save(context)
        return context

    def _get_handler(self, state: ConversationState):
        handlers = {
            ConversationState.MAIN_MENU: self._handle_main_menu,
            ConversationState.OPENING_MODE_SELECTION: self._handle_opening_mode,
            ConversationState.QUICK_DESCRIPTION_COLLECTION: (
                self._handle_quick_description
            ),
            ConversationState.QUICK_CATEGORY_CONFIRMATION: (
                self._handle_quick_category_confirmation
            ),
            ConversationState.CATEGORY_SELECTION: self._handle_category_selection,
            ConversationState.OTHER_CATEGORY_TEXT: self._handle_other_category_text,
            ConversationState.OTHER_CATEGORY_CONFIRMATION: (
                self._handle_other_category_confirmation
            ),
            ConversationState.DESCRIPTION_COLLECTION: self._handle_description,
            ConversationState.DESCRIPTION_REVIEW: self._handle_description_review,
            ConversationState.IMPACT_SELECTION: self._handle_impact,
            ConversationState.LOCATION_COLLECTION: self._handle_location,
            ConversationState.EVIDENCE_DECISION: self._handle_evidence_decision,
            ConversationState.EVIDENCE_COLLECTION: self._handle_evidence_text,
            ConversationState.FINAL_CONFIRMATION: self._handle_final_confirmation,
            ConversationState.QUERY_MENU: self._handle_query_menu,
            ConversationState.QUERY_TICKET_NUMBER: self._handle_query_ticket_number,
            ConversationState.COMPLEMENT_TICKET_NUMBER: (
                self._handle_complement_ticket_number
            ),
            ConversationState.COMPLEMENT_TEXT_COLLECTION: (
                self._handle_complement_text
            ),
            ConversationState.COMPLEMENT_REVIEW: self._handle_complement_review,
            ConversationState.EXITED: self._handle_exited,
        }
        return handlers[state]

    def _handle_main_menu(
        self, context: ConversationContext, message: str
    ) -> ConversationTurnResult:
        choice = self.parser.parse_choice(message)
        if choice == 1:
            context.reset_ticket_draft()
            self.state_machine.transition_to(
                context, ConversationState.OPENING_MODE_SELECTION
            )
            return self._result(context, build_opening_mode_menu())
        if choice == 2:
            self.state_machine.transition_to(context, ConversationState.QUERY_MENU)
            return self._result(context, build_query_menu())
        if choice == 3:
            self.state_machine.transition_to(
                context, ConversationState.COMPLEMENT_TICKET_NUMBER
            )
            return self._result(
                context,
                "🔢 Informe o **número do chamado** que deseja complementar.",
            )
        if choice == 4:
            self.state_machine.transition_to(context, ConversationState.EXITED)
            return self._result(
                context,
                "🚪 **Sessão encerrada.** Envie qualquer mensagem quando quiser iniciar novamente.",
            )
        return self._result(
            context,
            build_invalid_option_message() + "\n\n" + build_main_menu(context.user),
        )

    def _handle_opening_mode(
        self, context: ConversationContext, message: str
    ) -> ConversationTurnResult:
        choice = self.parser.parse_choice(message)
        if choice == 1:
            context.reset_ticket_draft()
            context.opening_mode = TicketOpeningMode.QUICK.value
            self.state_machine.transition_to(
                context, ConversationState.QUICK_DESCRIPTION_COLLECTION
            )
            return self._result(
                context,
                "⚡ Descreva em poucas palavras o problema ou solicitação.",
            )
        if choice == 2:
            context.reset_ticket_draft()
            context.opening_mode = TicketOpeningMode.DETAILED.value
            self.state_machine.transition_to(context, ConversationState.CATEGORY_SELECTION)
            return self._result(context, render_category_menu())
        if choice == 3:
            context.move_to_main_menu()
            return self._result(context, build_main_menu(context.user))
        return self._result(
            context,
            build_invalid_option_message() + "\n\n" + build_opening_mode_menu(),
        )

    def _handle_quick_description(
        self, context: ConversationContext, message: str
    ) -> ConversationTurnResult:
        context.original_description = message
        organization = self._organize_description(
            context,
            message,
            purpose="descricao_chamado_rapido",
        )
        if organization.needs_clarification:
            return self._result(context, organization.clarification_question)
        context.organized_description = organization.organized_text
        category_match = self.category_matching_service.find_best_match(message)
        context.pending_category_suggestion_id = category_match.category_id
        context.pending_category_suggestion_name = category_match.category_name
        self.state_machine.transition_to(
            context, ConversationState.QUICK_CATEGORY_CONFIRMATION
        )
        return self._result(
            context,
            "🤖 **Identifiquei uma categoria provável:**\n\n"
            f"{category_match.category_id}. **{category_match.category_name}**\n\n"
            "Podemos seguir com ela?\n\n"
            "1. ✅ **Sim**\n"
            "2. 📚 **Escolher categoria manualmente**\n"
            "3. 🧰 **Manter como Outro**\n"
            "4. ❌ **Cancelar chamado**",
        )

    def _handle_quick_category_confirmation(
        self, context: ConversationContext, message: str
    ) -> ConversationTurnResult:
        choice = self.parser.parse_choice(message)
        if choice == 1:
            self._apply_pending_category(context)
            self.state_machine.transition_to(context, ConversationState.DESCRIPTION_REVIEW)
            return self._result(
                context,
                build_description_review_message(context.organized_description or ""),
            )
        if choice == 2:
            self.state_machine.transition_to(context, ConversationState.CATEGORY_SELECTION)
            return self._result(
                context,
                "Escolha a categoria manualmente.\n\n" + render_category_menu(),
            )
        if choice == 3:
            self._set_category(context, 12)
            self.state_machine.transition_to(context, ConversationState.DESCRIPTION_REVIEW)
            return self._result(
                context,
                build_description_review_message(context.organized_description or ""),
            )
        if choice == 4:
            context.move_to_main_menu()
            return self._result(
                context,
                "❌ **Chamado cancelado com segurança.**\n\n" + build_main_menu(context.user),
            )
        return self._result(context, build_invalid_option_message())

    def _handle_category_selection(
        self, context: ConversationContext, message: str
    ) -> ConversationTurnResult:
        choice = self.parser.parse_choice(message)
        category = get_category_by_id(choice or 0)
        if category is None:
            return self._result(
                context,
                build_invalid_option_message() + "\n\n" + render_category_menu(),
            )

        if category.id == 12 and not context.original_description:
            self.state_machine.transition_to(context, ConversationState.OTHER_CATEGORY_TEXT)
            return self._result(
                context,
                "Descreva em poucas palavras o tipo de problema:",
            )

        self._set_category(context, category.id)
        if context.original_description and context.organized_description:
            self.state_machine.transition_to(context, ConversationState.DESCRIPTION_REVIEW)
            return self._result(
                context,
                build_description_review_message(context.organized_description),
            )

        self.state_machine.transition_to(context, ConversationState.DESCRIPTION_COLLECTION)
        return self._result(context, render_description_prompt(category))

    def _handle_other_category_text(
        self, context: ConversationContext, message: str
    ) -> ConversationTurnResult:
        category_match = self.category_matching_service.find_best_match(message)
        context.pending_category_suggestion_id = category_match.category_id
        context.pending_category_suggestion_name = category_match.category_name
        self.state_machine.transition_to(
            context, ConversationState.OTHER_CATEGORY_CONFIRMATION
        )
        return self._result(
            context,
            "🤖 **Entendi que isso parece estar relacionado a:**\n\n"
            f"{category_match.category_id}. **{category_match.category_name}**\n\n"
            "Confirma essa categoria?\n\n"
            "1. ✅ **Sim**\n"
            "2. 🧰 **Não, manter como Outro**\n"
            "3. 📚 **Escolher outra categoria**",
        )

    def _handle_other_category_confirmation(
        self, context: ConversationContext, message: str
    ) -> ConversationTurnResult:
        choice = self.parser.parse_choice(message)
        if choice == 1:
            self._apply_pending_category(context)
            category = get_category_by_id(context.selected_category_id or 12)
            self.state_machine.transition_to(context, ConversationState.DESCRIPTION_COLLECTION)
            return self._result(context, render_description_prompt(category))
        if choice == 2:
            self._set_category(context, 12)
            category = get_category_by_id(12)
            self.state_machine.transition_to(context, ConversationState.DESCRIPTION_COLLECTION)
            return self._result(context, render_description_prompt(category))
        if choice == 3:
            self.state_machine.transition_to(context, ConversationState.CATEGORY_SELECTION)
            return self._result(context, render_category_menu())
        return self._result(context, build_invalid_option_message())

    def _handle_description(
        self, context: ConversationContext, message: str
    ) -> ConversationTurnResult:
        context.original_description = message
        organization = self._organize_description(
            context,
            message,
            purpose="descricao_chamado",
        )
        if organization.needs_clarification:
            return self._result(context, organization.clarification_question)
        context.organized_description = organization.organized_text
        self.state_machine.transition_to(context, ConversationState.DESCRIPTION_REVIEW)
        return self._result(
            context,
            build_description_review_message(context.organized_description),
        )

    def _handle_description_review(
        self, context: ConversationContext, message: str
    ) -> ConversationTurnResult:
        choice = self.parser.parse_choice(message)
        if choice == 1:
            self.state_machine.transition_to(context, ConversationState.IMPACT_SELECTION)
            return self._result(context, render_impact_menu())
        if choice == 2:
            self.state_machine.transition_to(context, ConversationState.DESCRIPTION_COLLECTION)
            category = get_category_by_id(context.selected_category_id or 12)
            return self._result(context, render_description_prompt(category))
        if choice == 3:
            context.organized_description = context.original_description
            self.state_machine.transition_to(context, ConversationState.IMPACT_SELECTION)
            return self._result(context, render_impact_menu())
        if choice == 4:
            context.move_to_main_menu()
            return self._result(
                context,
                "❌ **Chamado cancelado com segurança.**\n\n" + build_main_menu(context.user),
            )
        return self._result(context, build_invalid_option_message())

    def _handle_impact(
        self, context: ConversationContext, message: str
    ) -> ConversationTurnResult:
        choice = self.parser.parse_choice(message)
        impact = get_impact_by_id(choice or 0)
        if impact is None:
            return self._result(
                context,
                build_invalid_option_message() + "\n\n" + render_impact_menu(),
            )

        context.impact_id = impact.id
        context.impact_label = impact.label
        context.severity = self.severity_mapping_service.map_impact_to_severity(
            impact.id
        )
        self.state_machine.transition_to(context, ConversationState.LOCATION_COLLECTION)
        return self._result(context, build_location_prompt())

    def _handle_location(
        self, context: ConversationContext, message: str
    ) -> ConversationTurnResult:
        context.location = message
        self.state_machine.transition_to(context, ConversationState.EVIDENCE_DECISION)
        return self._result(context, build_evidence_question())

    def _handle_evidence_decision(
        self, context: ConversationContext, message: str
    ) -> ConversationTurnResult:
        choice = self.parser.parse_choice(message)
        if choice == 1:
            self.state_machine.transition_to(context, ConversationState.EVIDENCE_COLLECTION)
            return self._result(
                context,
                "📎 Descreva o erro, print ou informação adicional. No simulador web, envie apenas texto.",
            )
        if choice == 2:
            context.evidence = "Não informado"
            return self._prepare_final_summary(context)
        return self._result(context, build_invalid_option_message())

    def _handle_evidence_text(
        self, context: ConversationContext, message: str
    ) -> ConversationTurnResult:
        organization = self._organize_description(
            context,
            message,
            purpose="evidencia_textual",
        )
        if organization.needs_clarification:
            return self._result(context, organization.clarification_question)
        context.evidence = organization.organized_text
        return self._prepare_final_summary(context)

    def _handle_final_confirmation(
        self, context: ConversationContext, message: str
    ) -> ConversationTurnResult:
        choice = self.parser.parse_choice(message)
        if choice == 1:
            draft = self.ticket_factory.create_draft_from_context(context)
            payload = self.glpi_payload_builder.build_from_ticket_draft(draft)
            created_ticket = self.glpi_client.create_ticket(payload)
            created_ticket_data = created_ticket.to_dict()
            context.move_to_main_menu()
            return self._result(
                context,
                "✅ **Chamado simulado criado com sucesso.**\n\n"
                f"🔢 **Número simulado:** {created_ticket.ticket_number}\n"
                f"🏷️ **Título:** {created_ticket.title}\n"
                f"📌 **Status:** {created_ticket.status}\n"
                f"🚦 **Gravidade:** {created_ticket.severity}\n"
                f"📝 **Descrição organizada:** {created_ticket.description}\n\n"
                + build_main_menu(context.user),
                created_ticket=created_ticket_data,
            )
        if choice == 2:
            self.state_machine.transition_to(context, ConversationState.CATEGORY_SELECTION)
            return self._result(
                context,
                "✏️ **Vamos corrigir as informações do chamado.**\n\n" + render_category_menu(),
                ticket_preview=context.ticket_preview,
            )
        if choice == 3:
            context.move_to_main_menu()
            return self._result(
                context,
                "❌ **Chamado cancelado com segurança.**\n\n" + build_main_menu(context.user),
            )
        return self._result(context, build_invalid_option_message())

    def _handle_query_menu(
        self, context: ConversationContext, message: str
    ) -> ConversationTurnResult:
        choice = self.parser.parse_choice(message)
        if choice == 1:
            return self._render_ticket_list(
                context,
                title="Meus chamados abertos",
                status_filter=TicketStatus.OPEN.value,
            )
        if choice == 2:
            return self._render_ticket_list(
                context,
                title="Meus chamados em atendimento",
                status_filter=TicketStatus.IN_PROGRESS.value,
            )
        if choice == 3:
            return self._render_ticket_list(
                context,
                title="Meus últimos chamados",
                status_filter=None,
            )
        if choice == 4:
            self.state_machine.transition_to(context, ConversationState.QUERY_TICKET_NUMBER)
            return self._result(context, "🔢 Informe o **número do chamado**.")
        if choice == 5:
            context.move_to_main_menu()
            return self._result(context, build_main_menu(context.user))
        return self._result(
            context,
            build_invalid_option_message() + "\n\n" + build_query_menu(),
        )

    def _handle_query_ticket_number(
        self, context: ConversationContext, message: str
    ) -> ConversationTurnResult:
        ticket_number = self.parser.parse_ticket_number(message)
        if ticket_number is None:
            return self._result(context, "🔢 Informe apenas o **número do chamado**.")

        ticket = self.glpi_client.get_ticket_by_id(
            ticket_number, context.user.glpi_user_id
        )
        if not self.user_scope_guard.can_access_ticket(
            context.user.glpi_user_id, ticket
        ):
            self.state_machine.transition_to(context, ConversationState.QUERY_MENU)
            return self._result(
                context,
                "🔎 Não localizei esse chamado entre os seus chamados.\n\n"
                + build_query_menu(),
            )

        self.state_machine.transition_to(context, ConversationState.QUERY_MENU)
        return self._result(
            context,
            self._render_ticket_detail(ticket) + "\n\n" + build_query_menu(),
        )

    def _handle_complement_ticket_number(
        self, context: ConversationContext, message: str
    ) -> ConversationTurnResult:
        ticket_number = self.parser.parse_ticket_number(message)
        if ticket_number is None:
            return self._result(context, "🔢 Informe apenas o **número do chamado**.")

        ticket = self.glpi_client.get_ticket_by_id(
            ticket_number, context.user.glpi_user_id
        )
        if not self.user_scope_guard.can_access_ticket(
            context.user.glpi_user_id, ticket
        ):
            context.move_to_main_menu()
            return self._result(
                context,
                "🔎 Não localizei esse chamado entre os seus chamados disponíveis para complemento.\n\n"
                + build_main_menu(context.user),
            )

        if ticket.status not in {TicketStatus.OPEN.value, TicketStatus.IN_PROGRESS.value}:
            context.move_to_main_menu()
            return self._result(
                context,
                "⚠️ Esse chamado não está aberto ou em atendimento para receber complemento.\n\n"
                + build_main_menu(context.user),
            )

        context.ticket_to_complement_id = ticket.ticket_number
        self.state_machine.transition_to(
            context, ConversationState.COMPLEMENT_TEXT_COLLECTION
        )
        return self._result(
            context,
            "📝 Digite o complemento que deseja adicionar ao chamado.",
        )

    def _handle_complement_text(
        self, context: ConversationContext, message: str
    ) -> ConversationTurnResult:
        context.complement_original_text = message
        organization = self._organize_description(
            context,
            message,
            purpose="complemento_chamado",
        )
        if organization.needs_clarification:
            return self._result(context, organization.clarification_question)
        context.complement_rewritten_text = organization.organized_text
        self.state_machine.transition_to(context, ConversationState.COMPLEMENT_REVIEW)
        return self._result(
            context,
            build_complement_review_message(context.complement_rewritten_text),
        )

    def _handle_complement_review(
        self, context: ConversationContext, message: str
    ) -> ConversationTurnResult:
        choice = self.parser.parse_choice(message)
        if choice == 1:
            return self._create_followup(
                context,
                context.complement_rewritten_text or "",
            )
        if choice == 2:
            self.state_machine.transition_to(
                context, ConversationState.COMPLEMENT_TEXT_COLLECTION
            )
            return self._result(
                context,
                "✍️ Digite novamente o complemento que deseja adicionar.",
            )
        if choice == 3:
            return self._create_followup(
                context,
                context.complement_original_text or "",
            )
        if choice == 4:
            context.move_to_main_menu()
            return self._result(
                context,
                "❌ **Complemento cancelado com segurança.**\n\n" + build_main_menu(context.user),
            )
        return self._result(context, build_invalid_option_message())

    def _handle_exited(
        self, context: ConversationContext, message: str
    ) -> ConversationTurnResult:
        context.move_to_main_menu()
        return self._result(context, build_main_menu(context.user))

    def _prepare_final_summary(
        self, context: ConversationContext
    ) -> ConversationTurnResult:
        context.suggested_title = self.title_generation_service.generate_title(
            context.selected_category_name or "Chamado",
            context.organized_description or context.original_description or "",
        )
        summary = self.ticket_summary_builder.build_summary(context)
        context.ticket_preview = summary.to_dict()
        self.state_machine.transition_to(context, ConversationState.FINAL_CONFIRMATION)
        return self._result(
            context,
            self.ticket_summary_builder.render_summary_message(summary),
            ticket_preview=context.ticket_preview,
        )

    def _organize_description(
        self,
        context: ConversationContext,
        message: str,
        purpose: str,
    ) -> DescriptionOrganizationResult:
        try:
            return self.description_organizer.organize_ticket_description(
                user_text=message,
                category_name=context.selected_category_name,
                purpose=purpose,
            )
        except LocalGenerativeAIUnavailableError:
            logger.exception(
                "local_generative_ai_unavailable",
                extra={"session_id": context.session_id, "state": context.state.value},
            )
            return DescriptionOrganizationResult(
                status="needs_clarification",
                organized_text="",
                clarification_question=(
                    "🤖 A IA generativa local não está disponível agora. "
                    "Verifique o Ollama/modelo local e envie a descrição novamente."
                ),
                confidence=0.0,
                backend="unavailable",
            )

    def _render_ticket_list(
        self,
        context: ConversationContext,
        title: str,
        status_filter: str | None,
    ) -> ConversationTurnResult:
        tickets = self.glpi_client.get_my_tickets(context.user.glpi_user_id)
        visible_tickets = self.user_scope_guard.filter_tickets_for_user(
            context.user.glpi_user_id, tickets
        )
        if status_filter:
            visible_tickets = [
                ticket for ticket in visible_tickets if ticket.status == status_filter
            ]
        visible_tickets = visible_tickets[:5]

        if not visible_tickets:
            return self._result(
                context,
                f"🔎 **{title}:**\n\nNão encontrei chamados para essa consulta.\n\n"
                + build_query_menu(),
            )

        lines = [f"{title}:"]
        for ticket in visible_tickets:
            lines.append(
                f"#{ticket.ticket_number} - **{ticket.title}**\n"
                f"📌 Status: {ticket.status} | 🚦 Gravidade: {ticket.severity}"
            )
        lines.append("")
        lines.append(build_query_menu())
        return self._result(context, "\n\n".join(lines))

    def _render_ticket_detail(self, ticket) -> str:
        return (
            f"🎫 **Chamado #{ticket.ticket_number}**\n"
            f"🏷️ **Título:** {ticket.title}\n"
            f"📌 **Status:** {ticket.status}\n"
            f"📚 **Categoria:** {ticket.category_name}\n"
            f"🚦 **Gravidade:** {ticket.severity}\n"
            f"📝 **Descrição:** {ticket.description}\n"
            f"💬 **Complementos:** {len(ticket.followups)}"
        )

    def _create_followup(
        self, context: ConversationContext, content: str
    ) -> ConversationTurnResult:
        followup = self.glpi_client.add_followup(
            context.ticket_to_complement_id or 0,
            context.user.glpi_user_id,
            content,
        )
        context.move_to_main_menu()
        if followup is None:
            return self._result(
                context,
                "🔎 Não localizei esse chamado entre os seus chamados disponíveis para complemento.\n\n"
                + build_main_menu(context.user),
            )
        return self._result(
            context,
            "✅ **Complemento simulado adicionado com sucesso.**\n\n"
            + build_main_menu(context.user),
        )

    def _set_category(self, context: ConversationContext, category_id: int) -> None:
        category = get_category_by_id(category_id)
        if category is None:
            category = get_category_by_id(12)
        context.selected_category_id = category.id
        context.selected_category_name = category.name

    def _apply_pending_category(self, context: ConversationContext) -> None:
        self._set_category(context, context.pending_category_suggestion_id or 12)

    def _result(
        self,
        context: ConversationContext,
        bot_message: str,
        ticket_preview: dict | None = None,
        created_ticket: dict | None = None,
    ) -> ConversationTurnResult:
        return ConversationTurnResult(
            session_id=context.session_id,
            bot_message=bot_message,
            state=context.state.value,
            ticket_preview=ticket_preview,
            created_ticket=created_ticket,
        )
