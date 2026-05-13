import hashlib
import json
import logging
import re
import time
import unicodedata
from uuid import uuid4

from app.application_config.settings import AppSettings, load_settings
from app.authentication_and_identity.simulated_auth_service import SimulatedAuthService
from app.background_jobs.celery_description_organizer import CeleryDescriptionOrganizer
from app.background_jobs.celery_ticket_detailer import CeleryTicketDetailer
from app.authentication_and_identity.channel_linking_factory import build_channel_linking_service
from app.conversation_engine.conversation_context import ConversationContext
from app.conversation_engine.conversation_input_parser import ConversationInputParser
from app.conversation_engine.conversation_menu_validator import ConversationMenuValidator
from app.conversation_engine.conversation_messages import (
    build_complement_review_message,
    build_description_clarification_message,
    build_description_review_message,
    build_evidence_question,
    build_invalid_option_message,
    build_location_prompt,
    build_main_menu,
    build_open_ticket_prompt,
    build_query_menu,
    build_ticket_type_prompt,
)
from app.conversation_engine.conversation_state_machine import ConversationStateMachine
from app.conversation_engine.conversation_states import ConversationState
from app.distributed_runtime.runtime_factory import (
    build_conversation_store,
    build_idempotency_store,
    build_rate_limiter,
    build_session_lock,
)
from app.distributed_runtime.session_locks import BusySessionError
from app.distributed_runtime.category_usage_tracker import (
    build_category_usage_tracker,
)
from app.glpi_integration_reserved.glpi_category_catalog_service import (
    GLPICategoryOption,
    build_category_catalog_service,
)
from app.glpi_integration_reserved.glpi_client_factory import build_glpi_client
from app.glpi_integration_reserved.glpi_future_real_client import GLPIClientError
from app.glpi_integration_reserved.glpi_location_catalog_service import (
    GLPILocationCatalogServiceInterface,
    GLPILocationOption,
    build_location_catalog_service,
)
from app.glpi_integration_reserved.glpi_ticket_payload_builder import (
    GLPITicketPayloadBuilder,
)
from app.local_light_ai.description_organization_models import (
    DescriptionOrganizationResult,
    GuidedDetailingResult,
    LocalGenerativeAIUnavailableError,
)
from app.local_light_ai.generative_description_organizer import (
    GenerativeDescriptionOrganizer,
    build_generative_description_organizer,
)
from app.local_light_ai.guided_ticket_detailer import build_guided_ticket_detailer
from app.local_light_ai.guided_ticket_detailer import MockGuidedTicketDetailer
from app.security_and_abuse_protection.input_sanitizer import InputSanitizer
from app.security_and_abuse_protection.message_size_limiter import MessageSizeLimiter
from app.security_and_abuse_protection.suspicious_input_detector import (
    SuspiciousInputDetector,
)
from app.security_and_abuse_protection.user_scope_guard import UserScopeGuard
from app.shared_kernel.constants import DEFAULT_CHANNEL, SECURITY_BLOCK_MESSAGE
from app.shared_kernel.result_types import ConversationTurnResult
from app.ticket_notifications.integration import (
    register_ticket_opened_for_notifications,
)
from app.ticket_notifications.ticket_links import build_ticket_public_url
from app.simulated_persistence.in_memory_ticket_store import InMemoryTicketStore
from app.ticket_domain.ticket_enums import TicketOpeningMode, TicketStatus
from app.ticket_domain.ticket_factory import TicketFactory
from app.ticket_domain.ticket_summary_builder import TicketSummaryBuilder
from app.triage_rules.category_catalog import get_category_by_id, render_category_menu
from app.triage_rules.category_matching_service import CategoryMatchingService
from app.triage_rules.impact_catalog import get_impact_by_id, render_impact_menu
from app.triage_rules.severity_mapping_service import SeverityMappingService
from app.triage_rules.title_generation_service import TitleGenerationService
from app.local_light_ai.generative_category_suggester import build_generative_category_suggester
from app.local_light_ai.generative_title_generator import build_generative_title_generator
from app.triage_rules.glpi_category_suggestion_service import (
    build_glpi_category_suggestion_service,
)


logger = logging.getLogger(__name__)


class ConversationFlowController:
    def __init__(
        self,
        settings: AppSettings | None = None,
        auth_service: SimulatedAuthService | None = None,
        conversation_store=None,
        ticket_store: InMemoryTicketStore | None = None,
        glpi_client=None,
        description_organizer: GenerativeDescriptionOrganizer | None = None,
        description_detailer=None,
        location_service: GLPILocationCatalogServiceInterface | None = None,
        rate_limiter=None,
        session_lock=None,
        idempotency_store=None,
    ) -> None:
        self.settings = settings or load_settings()
        self.channel_linking_service = build_channel_linking_service(self.settings)
        self.ticket_store = ticket_store or InMemoryTicketStore()
        self.conversation_store = conversation_store or build_conversation_store(
            self.settings
        )
        self.glpi_client = glpi_client or build_glpi_client(
            self.settings,
            self.ticket_store,
        )
        self.parser = ConversationInputParser()
        self.menu_validator = ConversationMenuValidator(self.parser)
        self.state_machine = ConversationStateMachine()
        self.input_sanitizer = InputSanitizer()
        self.size_limiter = MessageSizeLimiter(self.settings.max_message_length)
        self.rate_limiter = rate_limiter or build_rate_limiter(self.settings)
        self.session_lock = session_lock or build_session_lock(self.settings)
        self.idempotency_store = idempotency_store or build_idempotency_store(
            self.settings
        )
        self.suspicious_detector = SuspiciousInputDetector()
        self.user_scope_guard = UserScopeGuard()
        self.category_catalog = build_category_catalog_service(self.settings)
        self.location_service = location_service or build_location_catalog_service(
            self.settings
        )
        self.category_usage_tracker = build_category_usage_tracker(self.settings)
        self.category_matching_service = (
            build_glpi_category_suggestion_service(
                self.settings,
                self.category_catalog,
            )
            if self.settings.is_glpi_real_mode
            else build_generative_category_suggester(self.settings)
        )
        self.severity_mapping_service = SeverityMappingService()
        self.title_generation_service = build_generative_title_generator(self.settings)
        self.ticket_summary_builder = TicketSummaryBuilder()
        self.ticket_factory = TicketFactory()
        self.glpi_payload_builder = GLPITicketPayloadBuilder(
            default_entity_id=self.settings.glpi_default_entity_id,
            default_requester_user_id=self.settings.glpi_default_requester_user_id,
            require_glpi_category=self.settings.is_glpi_real_mode,
        )
        self.description_organizer = description_organizer or (
            CeleryDescriptionOrganizer(self.settings)
            if self.settings.use_celery_workers
            else build_generative_description_organizer(self.settings)
        )
        self.description_detailer = None
        if self.settings.ai_guided_detailing_enabled:
            self.description_detailer = description_detailer or (
                CeleryTicketDetailer(self.settings)
                if self.settings.use_celery_workers
                else build_guided_ticket_detailer(self.settings)
            )

    def process_message(
        self,
        session_id: str,
        message: str,
        channel: str = DEFAULT_CHANNEL,
        channel_identifier: str = "",
        media: list[dict] | None = None,
    ) -> ConversationTurnResult:
        normalized_session_id = session_id.strip() or str(uuid4())
        try:
            with self.session_lock.lock(normalized_session_id):
                return self._process_message_locked(
                    normalized_session_id,
                    message,
                    channel,
                    channel_identifier,
                    media,
                )
        except BusySessionError:
            return ConversationTurnResult(
                session_id=normalized_session_id,
                bot_message=(
                    "Ainda estou processando sua resposta anterior. "
                    "Aguarde eu enviar a próxima mensagem antes de digitar outra opção."
                ),
                state="processing",
            )

    def _process_message_locked(
        self,
        session_id: str,
        message: str,
        channel: str,
        channel_identifier: str,
        media: list[dict] | None = None,
    ) -> ConversationTurnResult:
        
        auth_resolution = self.channel_linking_service.resolve_or_handle(channel, channel_identifier, message)
        
        if auth_resolution.requires_user_action:
            return self._result_no_context(session_id, auth_resolution.bot_message)
            
        context = self._get_or_create_context(
            session_id,
            channel,
            auth_resolution.user,
            channel_identifier=channel_identifier,
        )

        normalized_media = self._normalize_media_payloads(media)

        if self.parser.is_start_message(message) and not normalized_media:
            return self._result(context, self._build_main_menu(context.user))

        if self.parser.is_reset_command(message):
            context.move_to_main_menu()
            self.rate_limiter.reset(context.session_id)
            self.idempotency_store.clear(context.session_id)
            self.conversation_store.save(context)
            return self._result(
                context,
                "🔄 **Conversa reiniciada com segurança.**\n\n"
                + self._build_main_menu(context.user),
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
        if normalized_media:
            context.attachments.extend(normalized_media)
            if not sanitized_message:
                sanitized_message = "[Mídia anexada]"

        if not sanitized_message:
            return self._result(context, "Envie uma mensagem com texto para continuar.")

        handler = self._get_handler(context.state)
        result = handler(context, sanitized_message)
        self.conversation_store.save(context)
        logger.info(
            "conversation_turn_processed",
            extra={"session_id": context.session_id, "state": context.state.value},
        )
        return result

    def reset_conversation(
        self, session_id: str, channel: str = DEFAULT_CHANNEL, channel_identifier: str = ""
    ) -> ConversationTurnResult:
        normalized_session_id = session_id.strip() or str(uuid4())
        with self.session_lock.lock(normalized_session_id):
            self.conversation_store.delete(normalized_session_id)
            self.rate_limiter.reset(normalized_session_id)
            self.idempotency_store.clear(normalized_session_id)
            
            auth_resolution = self.channel_linking_service.resolve_or_handle(
                channel, channel_identifier, ""
            )
            
            if not auth_resolution.is_linked:
                return self._result_no_context(
                    normalized_session_id, 
                    "🔄 **Conversa reiniciada com segurança.**\n\n" + (auth_resolution.bot_message or "")
                )

            context = self._get_or_create_context(
                normalized_session_id,
                channel,
                auth_resolution.user,
                channel_identifier=channel_identifier,
            )
            return self._result(
                context,
                "🔄 **Conversa reiniciada com segurança.**\n\n"
                + self._build_main_menu(context.user),
            )

    def debug_session(self, session_id: str) -> dict | None:
        if not self.settings.expose_debug_routes:
            return {"detail": "debug_disabled"}
        return self.conversation_store.debug_context(session_id)

    def _get_or_create_context(
        self,
        session_id: str,
        channel: str,
        user=None,
        channel_identifier: str = "",
    ) -> ConversationContext:
        context = self.conversation_store.get(session_id)
        if context is not None:
            if user:
                if not context.user or context.user.glpi_user_id != user.glpi_user_id:
                    # If user changed unexpectedly or was missing, update it
                    context.user = user
            if channel_identifier and context.channel_identifier != channel_identifier:
                context.channel_identifier = channel_identifier
            return context

        context = ConversationContext(
            session_id=session_id,
            channel=channel,
            channel_identifier=channel_identifier,
            user=user,
            state=ConversationState.MAIN_MENU,
        )
        self.conversation_store.save(context)
        return context

    def _result_no_context(self, session_id: str, bot_message: str) -> ConversationTurnResult:
        return ConversationTurnResult(
            session_id=session_id,
            bot_message=bot_message,
            state="authentication"
        )

    def _normalize_media_payloads(self, media: list[dict] | None) -> list[dict]:
        normalized: list[dict] = []
        seen: set[tuple[str, str]] = set()
        for index, item in enumerate(media or [], start=1):
            data_base64 = str(
                item.get("data_base64") or item.get("base64_data") or ""
            ).strip()
            if not data_base64:
                continue
            file_name = str(item.get("file_name") or f"anexo-{index}").strip()
            mime_type = str(item.get("mime_type") or "application/octet-stream").strip()
            dedupe_key = (file_name, hashlib.sha256(data_base64.encode()).hexdigest())
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            normalized.append(
                {
                    "file_name": file_name,
                    "mime_type": mime_type,
                    "data_base64": data_base64,
                }
            )
        return normalized

    def _build_main_menu(self, user) -> str:
        return build_main_menu(
            user,
            opening_only=self.settings.is_glpi_real_mode,
        )

    def _get_handler(self, state: ConversationState):
        handlers = {
            ConversationState.MAIN_MENU: self._handle_main_menu,
            ConversationState.TICKET_TYPE_SELECTION: self._handle_ticket_type_selection,
            ConversationState.DESCRIPTION_COLLECTION: self._handle_description,
            ConversationState.DESCRIPTION_CLARIFICATION: (
                self._handle_description_clarification
            ),
            ConversationState.CATEGORY_SELECTION: self._handle_category_selection,
            ConversationState.OTHER_CATEGORY_TEXT: self._handle_other_category_text,
            ConversationState.OTHER_CATEGORY_CONFIRMATION: (
                self._handle_other_category_confirmation
            ),
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
        valid_choices = {1, 2} if self.settings.is_glpi_real_mode else {1, 2, 3, 4}
        validation = self.menu_validator.require_choice(message, valid_choices)
        if not validation.is_valid:
            return self._result(
                context,
                validation.message + "\n\n" + self._build_main_menu(context.user),
            )

        if validation.choice == 1:
            context.reset_ticket_draft()
            context.opening_mode = TicketOpeningMode.ASSISTED.value
            if self.settings.is_glpi_real_mode:
                self.state_machine.transition_to(
                    context,
                    ConversationState.TICKET_TYPE_SELECTION,
                )
                return self._result(context, build_ticket_type_prompt())
            self.state_machine.transition_to(
                context,
                ConversationState.DESCRIPTION_COLLECTION,
            )
            return self._result(context, build_open_ticket_prompt())
        if self.settings.is_glpi_real_mode and validation.choice == 2:
            self.state_machine.transition_to(context, ConversationState.EXITED)
            return self._result(
                context,
                "Sessao encerrada. Envie qualquer mensagem quando quiser iniciar novamente.",
            )
        if validation.choice == 2:
            self.state_machine.transition_to(context, ConversationState.QUERY_MENU)
            return self._result(context, build_query_menu())
        if validation.choice == 3:
            self.state_machine.transition_to(
                context,
                ConversationState.COMPLEMENT_TICKET_NUMBER,
            )
            return self._result(
                context,
                "🔢 Informe o **número do chamado** que deseja complementar.",
            )

        self.state_machine.transition_to(context, ConversationState.EXITED)
        return self._result(
            context,
            "🚪 **Sessão encerrada.** Envie qualquer mensagem quando quiser iniciar novamente.",
        )

    def _handle_ticket_type_selection(
        self, context: ConversationContext, message: str
    ) -> ConversationTurnResult:
        validation = self.menu_validator.require_choice(message, {1, 2})
        if not validation.is_valid:
            return self._result(
                context,
                validation.message + "\n\n" + build_ticket_type_prompt(),
            )
            
        context.ticket_type = validation.choice
        self.state_machine.transition_to(
            context,
            ConversationState.DESCRIPTION_COLLECTION,
        )
        return self._result(context, build_open_ticket_prompt())


    def _handle_description(
        self, context: ConversationContext, message: str
    ) -> ConversationTurnResult:
        context.original_description = message
        context.organized_description = None
        context.reset_description_clarification()

        if self.description_detailer is not None:
            detailing = self._detail_description(context)
            if detailing is not None and detailing.asks_next:
                context.description_clarification_question = detailing.next_question
                self.state_machine.transition_to(
                    context,
                    ConversationState.DESCRIPTION_CLARIFICATION,
                )
                return self._result(
                    context,
                    build_description_clarification_message(
                        detailing.next_question,
                        len(context.description_clarification_turns) + 1,
                        self.settings.ai_max_clarification_questions,
                    ),
                )
            if detailing is not None and detailing.is_ready:
                return self._finalize_guided_description(
                    context,
                    self._build_detailing_source_text(context),
                )
            return self._advance_from_organized_description(
                context,
                self._fallback_description_text(message),
                category_source_text=message,
            )

        return self._finalize_direct_description(context, message)

    def _handle_description_clarification(
        self, context: ConversationContext, message: str
    ) -> ConversationTurnResult:
        if self._is_skip_detailing_response(message):
            return self._finalize_guided_description(
                context,
                self._build_detailing_source_text(context),
            )

        current_question = (
            context.description_clarification_question
            or "Qual equipamento, sistema ou serviço está afetado?"
        )
        context.description_clarification_turns.append(
            {"question": current_question, "answer": message}
        )
        context.description_clarification_question = None

        if (
            len(context.description_clarification_turns)
            >= self.settings.ai_max_clarification_questions
        ):
            return self._finalize_guided_description(
                context,
                self._build_detailing_source_text(context),
            )

        detailing = self._detail_description(context)
        if detailing is not None and detailing.asks_next:
            context.description_clarification_question = detailing.next_question
            self.state_machine.transition_to(
                context,
                ConversationState.DESCRIPTION_CLARIFICATION,
            )
            return self._result(
                context,
                build_description_clarification_message(
                    detailing.next_question,
                    len(context.description_clarification_turns) + 1,
                    self.settings.ai_max_clarification_questions,
                ),
            )
        if detailing is not None and detailing.is_ready:
            return self._finalize_guided_description(
                context,
                self._build_detailing_source_text(context),
            )

        source_text = self._build_detailing_source_text(context)
        return self._advance_from_organized_description(
            context,
            self._fallback_description_text(source_text),
            category_source_text=source_text,
        )

    def _handle_category_selection(
        self, context: ConversationContext, message: str
    ) -> ConversationTurnResult:
        if self.settings.is_glpi_real_mode:
            return self._handle_real_category_selection(context, message)

        validation = self.menu_validator.require_choice(message, set(range(1, 10)))
        if not validation.is_valid:
            return self._result(
                context,
                validation.message + "\n\n" + render_category_menu(),
            )

        if validation.choice == 8:
            self.state_machine.transition_to(context, ConversationState.OTHER_CATEGORY_TEXT)
            return self._result(
                context,
                "Digite uma palavra para pesquisar as categorias do bot.",
            )
        if validation.choice == 9:
            context.move_to_main_menu()
            return self._result(context, self._build_main_menu(context.user))

        mapping = {1: 1, 2: 2, 3: 4, 4: 6, 5: 3, 6: 5, 7: 12}
        category_id = mapping.get(validation.choice, 12)
        self._set_category(context, category_id)
        self.state_machine.transition_to(context, ConversationState.DESCRIPTION_REVIEW)
        return self._result(
            context,
            self._build_description_review(context),
        )

    def _handle_real_category_selection(
        self,
        context: ConversationContext,
        message: str,
    ) -> ConversationTurnResult:
        choice = self.parser.parse_choice(message)
        if choice is None:
            self.state_machine.transition_to(context, ConversationState.OTHER_CATEGORY_TEXT)
            return self._handle_other_category_text(context, message)

        options = [
            GLPICategoryOption(**option)
            for option in context.category_selection_options
        ]
        if 1 <= choice <= len(options):
            self._set_glpi_category(context, options[choice - 1])
            self.state_machine.transition_to(context, ConversationState.DESCRIPTION_REVIEW)
            return self._result(
                context,
                self._build_description_review(context),
            )

        search_choice = len(options) + 1
        cancel_choice = len(options) + 2
        if choice == search_choice:
            self.state_machine.transition_to(context, ConversationState.OTHER_CATEGORY_TEXT)
            return self._result(
                context,
                "Digite uma palavra para pesquisar na árvore de categorias do GLPI. Exemplo: wifi, senha, impressora.",
            )
        if choice == cancel_choice:
            context.move_to_main_menu()
            return self._cancel_to_main_menu(context, "❌ **Chamado cancelado com segurança.**")

        return self._result(
            context,
            build_invalid_option_message() + "\n\n" + self._render_real_category_menu(context),
        )

    def _handle_other_category_text(
        self, context: ConversationContext, message: str
    ) -> ConversationTurnResult:
        if self.settings.is_glpi_real_mode:
            try:
                results = self.category_catalog.search(
                    message,
                    ticket_type=context.ticket_type,
                    limit=5,
                )
            except GLPIClientError:
                logger.exception(
                    "glpi_category_search_failed",
                    extra={"session_id": context.session_id},
                )
                return self._glpi_category_unavailable_result(
                    context,
                    "Não consegui pesquisar as categorias reais do GLPI agora.",
                )
            self.state_machine.transition_to(context, ConversationState.CATEGORY_SELECTION)
            if not results:
                return self._result(
                    context,
                    "Nao encontrei uma categoria GLPI com esse filtro.\n\n"
                    + self._render_real_category_menu(context),
                )
            return self._result(
                context,
                self._render_real_category_menu(
                    context,
                    categories=results,
                    title="Resultados encontrados para sua pesquisa:",
                ),
            )

        category_match = self.category_matching_service.find_best_match(message)
        context.pending_category_suggestion_id = category_match.category_id
        context.pending_category_suggestion_name = category_match.category_name
        self.state_machine.transition_to(
            context, ConversationState.OTHER_CATEGORY_CONFIRMATION
        )
        return self._result(
            context,
            "🔎 **Resultado da Busca**\n\n"
            "Encontrei uma correspondência para sua pesquisa:\n"
            f"📍 **{category_match.category_name}**\n\n"
            "Podemos usar esta categoria?\n\n"
            "1️⃣ **Sim, confirmar**\n"
            "2️⃣ **Não, pesquisar novamente**\n"
            "3️⃣ **Usar categoria \"Outros\"**",
        )

    def _handle_other_category_confirmation(
        self, context: ConversationContext, message: str
    ) -> ConversationTurnResult:
        validation = self.menu_validator.require_choice(message, {1, 2, 3})
        if not validation.is_valid:
            return self._result(context, validation.message)
        if validation.choice == 1:
            if not self._apply_pending_category(context):
                self.state_machine.transition_to(context, ConversationState.CATEGORY_SELECTION)
                return self._result(
                    context,
                    "Nao consegui validar a categoria sugerida no GLPI. "
                    "Escolha uma categoria real antes de abrir o chamado.\n\n"
                    + self._render_real_category_menu(context),
                )
            self.state_machine.transition_to(context, ConversationState.DESCRIPTION_REVIEW)
            return self._result(
                context,
                self._build_description_review(context),
            )
        if validation.choice == 2:
            self.state_machine.transition_to(context, ConversationState.OTHER_CATEGORY_TEXT)
            return self._result(
                context,
                "Digite uma palavra para pesquisar as categorias do bot.",
            )

        self._set_category(context, 12)
        self.state_machine.transition_to(context, ConversationState.DESCRIPTION_REVIEW)
        return self._result(
            context,
            self._build_description_review(context),
        )

    def _handle_description_review(
        self, context: ConversationContext, message: str
    ) -> ConversationTurnResult:
        validation = self.menu_validator.require_choice(message, {1, 2, 3, 4})
        if not validation.is_valid:
            return self._result(context, validation.message)
        if validation.choice == 1:
            self.state_machine.transition_to(context, ConversationState.IMPACT_SELECTION)
            return self._result(context, render_impact_menu())
        if validation.choice == 2:
            self._reset_description_for_rewrite(context)
            self.state_machine.transition_to(context, ConversationState.DESCRIPTION_COLLECTION)
            return self._result(context, build_open_ticket_prompt())
        if validation.choice == 3:
            context.organized_description = context.original_description
            self.state_machine.transition_to(context, ConversationState.IMPACT_SELECTION)
            return self._result(context, render_impact_menu())

        context.move_to_main_menu()
        return self._cancel_to_main_menu(context, "❌ **Chamado cancelado com segurança.**")

    def _handle_impact(
        self, context: ConversationContext, message: str
    ) -> ConversationTurnResult:
        validation = self.menu_validator.require_choice(message, {1, 2, 3, 4})
        if not validation.is_valid:
            return self._result(
                context,
                validation.message + "\n\n" + render_impact_menu(),
            )

        impact_mapping = {1: 1, 2: 2, 3: 3, 4: 5}
        mapped_choice = impact_mapping.get(validation.choice, 1)
        impact = get_impact_by_id(mapped_choice)
        context.impact_id = impact.id
        context.impact_label = impact.label
        context.severity = self.severity_mapping_service.map_impact_to_severity(
            impact.id
        )
        self.state_machine.transition_to(context, ConversationState.LOCATION_COLLECTION)
        context.awaiting_location_retry = False
        context.location_selection_options = self._build_location_selection_options()
        return self._result(
            context,
            build_location_prompt(options=context.location_selection_options),
        )

    def _handle_location(
        self, context: ConversationContext, message: str
    ) -> ConversationTurnResult:
        selected_choice = self.parser.parse_choice(message)
        if selected_choice is not None:
            selected_location = self._resolve_glpi_location_from_choice(
                context,
                selected_choice,
            )
            if selected_location is None:
                context.awaiting_location_retry = True
                return self._result(
                    context,
                    build_location_prompt(
                        retry=True,
                        options=context.location_selection_options,
                    ),
                )
            context.location = selected_location.display_name
            context.glpi_location_id = selected_location.id
            context.awaiting_location_retry = False
            self.state_machine.transition_to(context, ConversationState.EVIDENCE_DECISION)
            return self._result(context, build_evidence_question())

        normalized_message = message.strip()
        if not normalized_message:
            return self._result(
                context,
                build_location_prompt(
                    retry=context.awaiting_location_retry,
                    options=context.location_selection_options,
                ),
            )

        if self.settings.is_glpi_real_mode:
            resolved_location = self._resolve_glpi_location_from_text(normalized_message)
            if resolved_location is None:
                context.awaiting_location_retry = True
                return self._result(
                    context,
                    build_location_prompt(
                        retry=True,
                        options=context.location_selection_options,
                    ),
                )
            context.location = resolved_location.display_name
            context.glpi_location_id = resolved_location.id
            context.awaiting_location_retry = False
        else:
            context.location = normalized_message
            context.glpi_location_id = None

        self.state_machine.transition_to(context, ConversationState.EVIDENCE_DECISION)
        return self._result(context, build_evidence_question())

    def _is_evidence_done_command(self, message: str) -> bool:
        normalized = self._normalize_control_text(message)
        return normalized in {"pronto", "finalizar", "concluir", "ok"}

    def _append_evidence_text(self, context: ConversationContext, message: str) -> None:
        if message == "[Mídia anexada]":
            return
        current = (context.evidence or "").strip()
        next_text = message.strip()
        context.evidence = "\n".join(part for part in [current, next_text] if part)

    def _handle_evidence_decision(
        self, context: ConversationContext, message: str
    ) -> ConversationTurnResult:
        validation = self.menu_validator.require_choice(message, {1, 2})
        if not validation.is_valid:
            return self._result(
                context,
                validation.message + "\n\n" + build_evidence_question(),
            )
        if validation.choice == 1:
            self.state_machine.transition_to(context, ConversationState.EVIDENCE_COLLECTION)
            return self._result(
                context,
                "📤 **Espaço para Anexos**\n\n"
                "Pode enviar seus arquivos agora, como fotos, vídeos ou documentos.\n\n"
                "Quando terminar, digite **PRONTO**.",
            )
        context.evidence = "Não informado"
        return self._prepare_final_summary(context)

    def _handle_evidence_text(
        self, context: ConversationContext, message: str
    ) -> ConversationTurnResult:
        if self.parser.parse_choice(message) == 2 and not context.evidence and not context.attachments:
            context.evidence = "Não informado"
            return self._prepare_final_summary(context)

        if not self._is_evidence_done_command(message):
            self._append_evidence_text(context, message)
            attachment_count = len(context.attachments)
            return self._result(
                context,
                "Informação registrada.\n\n"
                f"✅ **Recebidos:** {attachment_count}\n\n"
                "Quando terminar de enviar tudo, digite **PRONTO**."
            )

        if not context.evidence and not context.attachments:
            return self._result(
                context,
                "Ainda não recebi texto nem anexo. Envie a informação adicional ou digite *2* para seguir sem evidências.",
            )

        if not context.evidence and context.attachments:
            context.evidence = "Anexos enviados pelo WhatsApp."
            return self._prepare_final_summary(context)

        organization = self._organize_description(
            context,
            context.evidence or "",
            purpose="evidencia_textual",
        )
        if organization.needs_clarification:
            return self._result(context, organization.clarification_question)
        context.evidence = organization.organized_text
        return self._prepare_final_summary(context)

    def _handle_final_confirmation(
        self, context: ConversationContext, message: str
    ) -> ConversationTurnResult:
        validation = self.menu_validator.require_choice(message, {1, 2, 3})
        if not validation.is_valid:
            return self._result(context, validation.message)

        if validation.choice == 1:
            return self._create_ticket(context)
        if validation.choice == 2:
            self.state_machine.transition_to(context, ConversationState.CATEGORY_SELECTION)
            category_menu = (
                self._render_real_category_menu(context)
                if self.settings.is_glpi_real_mode
                else render_category_menu()
            )
            return self._result(
                context,
                "✏️ **Vamos corrigir as informações do chamado.**\n\n"
                + category_menu,
                ticket_preview=context.ticket_preview,
            )

        context.move_to_main_menu()
        return self._cancel_to_main_menu(context, "❌ **Chamado cancelado com segurança.**")

    def _handle_query_menu(
        self, context: ConversationContext, message: str
    ) -> ConversationTurnResult:
        validation = self.menu_validator.require_choice(message, {1, 2, 3, 4, 5})
        if not validation.is_valid:
            return self._result(
                context,
                validation.message + "\n\n" + build_query_menu(),
            )

        if validation.choice == 1:
            return self._render_ticket_list(
                context,
                title="Meus chamados abertos",
                status_filter=TicketStatus.OPEN.value,
            )
        if validation.choice == 2:
            return self._render_ticket_list(
                context,
                title="Meus chamados em atendimento",
                status_filter=TicketStatus.IN_PROGRESS.value,
            )
        if validation.choice == 3:
            return self._render_ticket_list(
                context,
                title="Meus últimos chamados",
                status_filter=None,
            )
        if validation.choice == 4:
            self.state_machine.transition_to(context, ConversationState.QUERY_TICKET_NUMBER)
            return self._result(context, "🔢 Informe o **número do chamado**.")

        context.move_to_main_menu()
        return self._result(context, self._build_main_menu(context.user))

    def _handle_query_ticket_number(
        self, context: ConversationContext, message: str
    ) -> ConversationTurnResult:
        ticket_number = self.parser.parse_ticket_number(message)
        if ticket_number is None:
            return self._result(context, "🔢 Informe apenas o **número do chamado**.")

        try:
            ticket = self.glpi_client.get_ticket_by_id(
                ticket_number, context.user.glpi_user_id
            )
        except GLPIClientError:
            ticket = None

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

        try:
            ticket = self.glpi_client.get_ticket_by_id(
                ticket_number, context.user.glpi_user_id
            )
        except GLPIClientError:
            ticket = None

        if not self.user_scope_guard.can_access_ticket(
            context.user.glpi_user_id, ticket
        ):
            context.move_to_main_menu()
            return self._result(
                context,
                "🔎 Não localizei esse chamado entre os seus chamados disponíveis para complemento.\n\n"
                + self._build_main_menu(context.user),
            )

        if ticket.status not in {TicketStatus.OPEN.value, TicketStatus.IN_PROGRESS.value}:
            context.move_to_main_menu()
            return self._result(
                context,
                "⚠️ Esse chamado não está aberto ou em atendimento para receber complemento.\n\n"
                + self._build_main_menu(context.user),
            )

        context.ticket_to_complement_id = ticket.ticket_number
        self.state_machine.transition_to(
            context,
            ConversationState.COMPLEMENT_TEXT_COLLECTION,
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
        validation = self.menu_validator.require_choice(message, {1, 2, 3})
        if not validation.is_valid:
            return self._result(context, validation.message)
        if validation.choice == 1:
            return self._create_followup(
                context,
                context.complement_rewritten_text or "",
            )
        if validation.choice == 2:
            self.state_machine.transition_to(
                context,
                ConversationState.COMPLEMENT_TEXT_COLLECTION,
            )
            return self._result(
                context,
                "✍️ Digite novamente o complemento que deseja adicionar.",
            )
        context.move_to_main_menu()
        return self._cancel_to_main_menu(
            context,
            "❌ **Complemento cancelado com segurança.**",
        )

    def _handle_exited(
        self, context: ConversationContext, message: str
    ) -> ConversationTurnResult:
        context.move_to_main_menu()
        return self._result(context, self._build_main_menu(context.user))

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

    def _create_ticket(self, context: ConversationContext) -> ConversationTurnResult:
        if self.settings.is_glpi_real_mode and not context.selected_glpi_category_id:
            self.state_machine.transition_to(context, ConversationState.CATEGORY_SELECTION)
            return self._result(
                context,
                "Antes de abrir no GLPI, preciso de uma categoria real validada.\n\n"
                + self._render_real_category_menu(context),
            )
        if self.settings.is_glpi_real_mode and not context.glpi_location_id:
            self.state_machine.transition_to(context, ConversationState.LOCATION_COLLECTION)
            context.awaiting_location_retry = True
            return self._result(
                context,
                "Antes de abrir no GLPI, preciso de uma localidade válida.\n\n"
                + build_location_prompt(retry=True),
            )

        idempotency_key = self._ticket_idempotency_key(context)
        existing_ticket = self.idempotency_store.get_result(idempotency_key)
        if existing_ticket:
            context.move_to_main_menu()
            created_message = (
                "✅ **Esse chamado já foi registrado com segurança.**\n\n"
                + self._render_created_ticket_message(existing_ticket)
            )
            return self._result(
                context,
                created_message,
                bot_messages=[created_message, self._build_main_menu(context.user)],
                created_ticket=existing_ticket,
            )

        if not self.idempotency_store.reserve(idempotency_key):
            return self._result(
                context,
                "⏳ Já estou processando essa abertura. Aguarde alguns segundos antes de tentar novamente.",
            )

        try:
            draft = self.ticket_factory.create_draft_from_context(context)
            payload = self.glpi_payload_builder.build_from_ticket_draft(draft)
            created_ticket = self.glpi_client.create_ticket(payload)
        except (GLPIClientError, ValueError):
            logger.exception(
                "glpi_ticket_creation_failed",
                extra={"session_id": context.session_id},
            )
            return self._result(
                context,
                "⚠️ **Não consegui abrir o chamado no GLPI agora.**\n\n"
                "Seus dados continuam preenchidos nesta etapa, então você pode tentar novamente em instantes sem reescrever tudo.",
            )

        created_ticket_data = created_ticket.to_dict()
        self.idempotency_store.store_result(idempotency_key, created_ticket_data)
        if self.settings.is_glpi_real_mode and context.selected_glpi_category_id:
            self.category_usage_tracker.increment(context.selected_glpi_category_id)
        try:
            register_ticket_opened_for_notifications(
                settings=self.settings,
                context=context,
                created_ticket=created_ticket_data,
            )
        except Exception:
            logger.exception(
                "ticket_notification_registration_failed",
                extra={"session_id": context.session_id},
            )
        context.move_to_main_menu()
        created_message = self._render_created_ticket_message(created_ticket_data)
        return self._result(
            context,
            created_message,
            bot_messages=[created_message, self._build_main_menu(context.user)],
            created_ticket=created_ticket_data,
        )

    def _finalize_direct_description(
        self,
        context: ConversationContext,
        message: str,
    ) -> ConversationTurnResult:
        organization = self._organize_description(
            context,
            message,
            purpose="descricao_chamado",
        )
        if organization.needs_clarification:
            return self._result(context, organization.clarification_question)
        return self._advance_from_organized_description(
            context,
            organization.organized_text,
            category_source_text=organization.organized_text or message,
        )

    def _finalize_guided_description(
        self,
        context: ConversationContext,
        source_text: str,
    ) -> ConversationTurnResult:
        source_text = source_text.strip() or context.original_description or ""
        organization = self._organize_description(
            context,
            source_text,
            purpose="descricao_chamado_detalhada",
        )
        organized_text = (
            organization.organized_text
            if organization.is_organized
            else source_text
        )
        organized_text = self._preserve_guided_user_markers(context, organized_text)
        if not organized_text:
            self.state_machine.transition_to(
                context,
                ConversationState.DESCRIPTION_COLLECTION,
            )
            return self._result(
                context,
                "Não consegui montar a descrição. Pode explicar novamente o que precisa?",
            )
        return self._advance_from_organized_description(
            context,
            organized_text,
            category_source_text=organized_text,
        )

    def _advance_from_organized_description(
        self,
        context: ConversationContext,
        organized_text: str,
        category_source_text: str,
    ) -> ConversationTurnResult:
        context.organized_description = organized_text
        context.description_clarification_question = None

        if context.selected_category_id:
            self.state_machine.transition_to(context, ConversationState.DESCRIPTION_REVIEW)
            return self._result(
                context,
                self._build_description_review(context),
            )

        if self.settings.is_glpi_real_mode:
            try:
                category_match = self.category_matching_service.find_best_match(
                    category_source_text,
                    ticket_type=context.ticket_type,
                )
                category = self.category_catalog.get_by_id(category_match.category_id)
                if category is not None:
                    context.pending_glpi_category_id = category.id
                    context.pending_category_complete_name = category.complete_name
            except GLPIClientError:
                logger.exception(
                    "glpi_category_suggestion_failed",
                    extra={"session_id": context.session_id},
                )
                return self._glpi_category_unavailable_result(
                    context,
                    "Consegui organizar sua descrição, mas não consegui consultar as categorias reais do GLPI agora.",
                )
        else:
            category_match = self.category_matching_service.find_best_match(
                category_source_text
            )
        context.pending_category_suggestion_id = category_match.category_id
        context.pending_category_suggestion_name = category_match.category_name
        logger.info(
            "category_suggestion_completed",
            extra={
                "session_id": context.session_id,
                "state": context.state.value,
                "category_id": category_match.category_id,
                "category_source": category_match.matched_keyword,
                "confidence": category_match.confidence,
            },
        )
        if not self._apply_pending_category(context):
            self.state_machine.transition_to(context, ConversationState.CATEGORY_SELECTION)
            return self._result(
                context,
                "Não consegui validar a categoria sugerida no GLPI. "
                "Escolha uma categoria real antes de abrir o chamado.\n\n"
                + self._render_real_category_menu(context),
            )
        self.state_machine.transition_to(context, ConversationState.DESCRIPTION_REVIEW)
        return self._result(
            context,
            self._build_description_review(context),
        )

    def _detail_description(
        self,
        context: ConversationContext,
    ) -> GuidedDetailingResult | None:
        if self.description_detailer is None:
            return None
        started_at = time.perf_counter()
        try:
            result = self.description_detailer.detail_ticket_description(
                original_description=context.original_description or "",
                clarification_turns=context.description_clarification_turns,
                category_name=context.selected_category_name,
                max_questions=self.settings.ai_max_clarification_questions,
            )
            logger.info(
                "guided_detailing_completed",
                extra={
                    "session_id": context.session_id,
                    "state": context.state.value,
                    "purpose": "descricao_chamado_pergunta_guiada",
                    "task_duration_ms": int((time.perf_counter() - started_at) * 1000),
                    "backend": result.backend,
                    "status": result.status,
                },
            )
            return result
        except LocalGenerativeAIUnavailableError:
            logger.exception(
                "local_guided_detailing_unavailable",
                extra={"session_id": context.session_id, "state": context.state.value},
            )
            fallback_result = MockGuidedTicketDetailer(
                backend_name="local-guided-fallback"
            ).detail_ticket_description(
                original_description=context.original_description or "",
                clarification_turns=context.description_clarification_turns,
                category_name=context.selected_category_name,
                max_questions=self.settings.ai_max_clarification_questions,
            )
            logger.info(
                "guided_detailing_fallback_completed",
                extra={
                    "session_id": context.session_id,
                    "state": context.state.value,
                    "purpose": "descricao_chamado_pergunta_guiada",
                    "task_duration_ms": int((time.perf_counter() - started_at) * 1000),
                    "backend": fallback_result.backend,
                    "status": fallback_result.status,
                },
            )
            return fallback_result

    def _build_detailing_source_text(self, context: ConversationContext) -> str:
        original_description = self._clip_text(context.original_description or "", 400)
        if not context.description_clarification_turns:
            return original_description

        parts: list[str] = []
        has_severity_marker = bool(self._severity_marker_label(original_description))
        if original_description and (
            not self._original_description_is_generic_for_summary(original_description)
            or not has_severity_marker
        ):
            parts.append(original_description)

        for turn in context.description_clarification_turns:
            answer = self._clip_text(turn.get("answer", ""), 240)
            if answer:
                parts.append(self._clean_guided_answer_for_summary(answer))
        return self._join_first_person_summary(parts)

    @staticmethod
    def _clean_guided_answer_for_summary(answer: str) -> str:
        text = " ".join((answer or "").strip().split()).strip(" .")
        text = re.sub(
            r"^(estou\s+com\s+(?:um\s+)?problema\s+que|o\s+problema\s+(?:e|é)\s+que|(?:e|é)\s+que)\s+",
            "",
            text,
            flags=re.IGNORECASE,
        )
        if text:
            text = text[0].upper() + text[1:]
        return text

    @classmethod
    def _join_first_person_summary(cls, parts: list[str]) -> str:
        sentences = []
        seen: set[str] = set()
        for part in parts:
            text = " ".join((part or "").strip().split()).strip(" .")
            if not text:
                continue
            key = cls._normalize_control_text(text)
            if key in seen:
                continue
            seen.add(key)
            if text.endswith(("!", "?")):
                sentences.append(text)
            else:
                sentences.append(text + ".")
        return " ".join(sentences)

    def _reset_description_for_rewrite(self, context: ConversationContext) -> None:
        context.original_description = None
        context.organized_description = None
        context.pending_category_suggestion_id = None
        context.pending_category_suggestion_name = None
        context.pending_glpi_category_id = None
        context.pending_category_complete_name = None
        context.category_selection_options = []
        context.reset_description_clarification()

    def _is_skip_detailing_response(self, message: str) -> bool:
        normalized = self._normalize_control_text(message)
        skip_responses = {
            "nao sei",
            "nao sei informar",
            "nao tenho",
            "nao tenho essa informacao",
            "pular",
            "prosseguir",
            "continuar",
        }
        return normalized in skip_responses

    def _original_description_is_generic_for_summary(self, text: str) -> bool:
        normalized = self._normalize_control_text(text)
        generic_issue = bool(
            re.search(
                r"\b(problema|erro|dificuldade)(?:\s+\w+){0,3}\s+"
                r"(de|do|da|dos|das|no|na|nos|nas|com|em)\b",
                normalized,
            )
        )
        detail_markers = (
            "quando",
            "ao ",
            "aparece",
            "mensagem",
            "salvar",
            "emitir",
            "abrir",
            "acessar",
            "imprimir",
            "iniciar",
            "travando",
            "caindo",
            "lento",
            "bloqueado",
            "sem ",
        )
        return generic_issue and not any(marker in normalized for marker in detail_markers)

    def _preserve_guided_user_markers(
        self,
        context: ConversationContext,
        organized_text: str,
    ) -> str:
        severity_label = self._severity_marker_label(context.original_description or "")
        if not severity_label:
            return organized_text

        normalized_text = self._normalize_control_text(organized_text)
        if self._normalize_control_text(severity_label) in normalized_text:
            return organized_text

        suffix = f"Considero o problema {severity_label}."
        if organized_text.endswith((".", "!", "?")):
            return f"{organized_text} {suffix}"
        return f"{organized_text}. {suffix}"

    def _severity_marker_label(self, text: str) -> str:
        normalized = self._normalize_control_text(text)
        if "critico" in normalized or "critica" in normalized:
            return "crítico"
        if "urgente" in normalized:
            return "urgente"
        if "grave" in normalized:
            return "grave"
        return ""

    @staticmethod
    def _clip_text(text: str, max_chars: int) -> str:
        text = " ".join(text.split())
        if len(text) <= max_chars:
            return text
        return text[: max_chars - 3].rstrip() + "..."

    @staticmethod
    def _normalize_control_text(text: str) -> str:
        normalized = unicodedata.normalize("NFKD", text.casefold())
        normalized = "".join(
            char for char in normalized if not unicodedata.combining(char)
        )
        normalized = re.sub(r"[^\w\s]", " ", normalized)
        return re.sub(r"\s+", " ", normalized).strip()

    def _resolve_glpi_location_from_text(
        self,
        message: str,
    ) -> GLPILocationOption | None:
        for candidate in self._location_query_candidates(message):
            matches = self.location_service.search(candidate, limit=5)
            if matches:
                return matches[0]
        return None

    def _resolve_glpi_location_from_choice(
        self,
        context: ConversationContext,
        choice: int,
    ) -> GLPILocationOption | None:
        options = context.location_selection_options or self._build_location_selection_options()
        context.location_selection_options = options
        if choice < 1 or choice > len(options):
            return None
        selected = options[choice - 1]
        return self.location_service.get_by_id(int(selected["id"]))

    def _build_location_selection_options(self) -> list[dict[str, object]]:
        try:
            locations = self.location_service.get_locations()
        except Exception:
            logger.exception("location_options_load_failed")
            return []
        return [
            {
                "id": location.id,
                "display_name": location.display_name,
            }
            for location in locations[:8]
        ]

    def _location_query_candidates(self, message: str) -> list[str]:
        raw_candidates = [
            message.strip(),
            re.split(r"\s+-\s+", message, maxsplit=1)[0],
            re.split(r"\s*/\s*", message, maxsplit=1)[0],
            re.split(r"\s*,\s*", message, maxsplit=1)[0],
        ]
        candidates: list[str] = []
        seen: set[str] = set()
        for raw_candidate in raw_candidates:
            candidate = " ".join(raw_candidate.split())
            normalized = self._normalize_control_text(candidate)
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            candidates.append(candidate)
        return candidates

    def _build_description_review(self, context: ConversationContext) -> str:
        return build_description_review_message(
            context.organized_description or "",
            context.selected_category_name,
        )

    def _organize_description(
        self,
        context: ConversationContext,
        message: str,
        purpose: str,
    ) -> DescriptionOrganizationResult:
        started_at = time.perf_counter()
        try:
            result = self.description_organizer.organize_ticket_description(
                user_text=message,
                category_name=context.selected_category_name,
                purpose=purpose,
            )
            logger.info(
                "description_organization_completed",
                extra={
                    "session_id": context.session_id,
                    "state": context.state.value,
                    "purpose": purpose,
                    "task_duration_ms": int((time.perf_counter() - started_at) * 1000),
                    "backend": result.backend,
                    "status": result.status,
                },
            )
            return result
        except LocalGenerativeAIUnavailableError:
            logger.exception(
                "local_generative_ai_unavailable",
                extra={
                    "session_id": context.session_id,
                    "state": context.state.value,
                    "purpose": purpose,
                    "task_duration_ms": int((time.perf_counter() - started_at) * 1000),
                },
            )
            return DescriptionOrganizationResult(
                status="organized",
                organized_text=self._fallback_description_text(message),
                clarification_question="",
                confidence=0.35,
                backend="unavailable-fallback",
            )

    @staticmethod
    def _fallback_description_text(message: str) -> str:
        text = " ".join((message or "").strip().split())
        text = re.sub(r"^O usuario informou inicialmente:\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"^O usuário informou inicialmente:\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(
            r"\bDepois, acrescentou estes detalhes:\s*",
            ". ",
            text,
            flags=re.IGNORECASE,
        )
        text = re.sub(r"\b\d+\.\s+", "", text).strip(" .")
        if not text:
            return "Solicitacao sem descricao detalhada."
        if text.endswith((".", "!", "?")):
            return text
        return text + "."

    def _render_ticket_list(
        self,
        context: ConversationContext,
        title: str,
        status_filter: str | None,
    ) -> ConversationTurnResult:
        try:
            tickets = self.glpi_client.get_my_tickets(context.user.glpi_user_id)
        except GLPIClientError:
            tickets = []

        visible_tickets = self.user_scope_guard.filter_tickets_for_user(
            context.user.glpi_user_id,
            tickets,
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

        lines = [f"🎫 **{title}:**"]
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
        try:
            followup = self.glpi_client.add_followup(
                context.ticket_to_complement_id or 0,
                context.user.glpi_user_id,
                content,
            )
        except GLPIClientError:
            followup = None

        context.move_to_main_menu()
        if followup is None:
            return self._result(
                context,
                "🔎 Não localizei esse chamado entre os seus chamados disponíveis para complemento.\n\n"
                + self._build_main_menu(context.user),
            )
        message = (
            "✅ **Complemento adicionado com sucesso.**\n\n"
            if self.settings.is_glpi_real_mode
            else "✅ **Complemento simulado adicionado com sucesso.**\n\n"
        )
        return self._result(context, message + self._build_main_menu(context.user))

    def _set_category(self, context: ConversationContext, category_id: int) -> None:
        if self.settings.is_glpi_real_mode:
            category = self.category_catalog.get_by_id(659)
            if category is None:
                categories = self.category_catalog.get_categories(context.ticket_type)
                category = categories[0] if categories else None
            if category is not None:
                self._set_glpi_category(context, category)
                return

        category = get_category_by_id(category_id) or get_category_by_id(12)
        context.selected_category_id = category.id
        context.selected_category_name = category.name

    def _apply_pending_category(self, context: ConversationContext) -> bool:
        if self.settings.is_glpi_real_mode:
            category_id = context.pending_glpi_category_id or context.pending_category_suggestion_id
            try:
                category = self.category_catalog.get_by_id(category_id or 0)
            except GLPIClientError:
                logger.exception(
                    "glpi_pending_category_validation_failed",
                    extra={"session_id": context.session_id},
                )
                return False
            if category is not None:
                self._set_glpi_category(context, category)
                return True
            return False
        self._set_category(context, context.pending_category_suggestion_id or 12)
        return True

    def _set_glpi_category(
        self,
        context: ConversationContext,
        category: GLPICategoryOption,
    ) -> None:
        context.selected_category_id = category.id
        context.selected_category_name = category.display_name
        context.selected_glpi_category_id = category.id
        context.selected_category_complete_name = category.complete_name

    def _render_real_category_menu(
        self,
        context: ConversationContext,
        *,
        categories: list[GLPICategoryOption] | None = None,
        title: str = "Categorias GLPI mais usadas no bot:",
    ) -> str:
        try:
            categories = categories or self.category_usage_tracker.top_categories(
                self.category_catalog,
                ticket_type=context.ticket_type,
                limit=5,
            )
        except GLPIClientError:
            logger.exception(
                "glpi_category_menu_failed",
                extra={"session_id": context.session_id},
            )
            context.category_selection_options = []
            return (
                "Não consegui carregar as categorias reais do GLPI agora. "
                "Tente novamente em instantes."
            )
        context.category_selection_options = [self._category_to_context_dict(category) for category in categories[:5]]
        if not context.category_selection_options:
            return (
                "Não consegui carregar as categorias reais do GLPI agora. "
                "Tente novamente em instantes."
            )

        lines = [
            f"**{title}**",
            "",
            "Digite no teclado o **número** da opção desejada:",
        ]
        for index, category in enumerate(categories[:5], start=1):
            lines.append(f"{self._keycap(index)} **{category.display_name}**")
        lines.append(f"{self._keycap(len(context.category_selection_options) + 1)} **Pesquisar categoria**")
        lines.append(f"{self._keycap(len(context.category_selection_options) + 2)} **Cancelar chamado**")
        return "\n".join(lines)

    @staticmethod
    def _category_to_context_dict(category: GLPICategoryOption) -> dict:
        return {
            "id": category.id,
            "name": category.name,
            "complete_name": category.complete_name,
            "entity_id": category.entity_id,
            "parent_id": category.parent_id,
            "level": category.level,
            "is_helpdesk_visible": category.is_helpdesk_visible,
            "is_incident": category.is_incident,
            "is_request": category.is_request,
        }

    def _glpi_category_unavailable_result(
        self,
        context: ConversationContext,
        message: str,
    ) -> ConversationTurnResult:
        self.state_machine.transition_to(context, ConversationState.CATEGORY_SELECTION)
        return self._result(
            context,
            message + "\n\nNão vou perder sua descrição. Tente novamente em instantes.",
        )

    @staticmethod
    def _keycap(number: int) -> str:
        keycaps = {
            1: "1️⃣",
            2: "2️⃣",
            3: "3️⃣",
            4: "4️⃣",
            5: "5️⃣",
            6: "6️⃣",
            7: "7️⃣",
        }
        return keycaps.get(number, str(number))

    def _ticket_idempotency_key(self, context: ConversationContext) -> str:
        payload = {
            "session_id": context.session_id,
            "preview": context.ticket_preview,
            "description": context.organized_description,
            "category": context.selected_category_id,
            "glpi_category": context.selected_glpi_category_id,
        }
        digest = hashlib.sha256(
            json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
        ).hexdigest()
        return f"{context.session_id}:{digest}"

    def _render_created_ticket_message(self, created_ticket: dict) -> str:
        category = created_ticket.get("category") or created_ticket.get("category_name") or "Suporte TI"
        ticket_number = created_ticket["ticket_number"]
        ticket_url = build_ticket_public_url(
            self.settings.glpi_ticket_public_url_template,
            ticket_number,
        )
        expected_attachments = int(created_ticket.get("attachments_expected_count") or 0)
        uploaded_attachments = int(created_ticket.get("attachments_uploaded_count") or 0)
        attachment_errors = [str(item) for item in created_ticket.get("attachment_errors") or []]
        if expected_attachments:
            attachment_line = f"\n📎 **Anexos vinculados:** {uploaded_attachments}/{expected_attachments}"
        else:
            attachment_line = ""
        if attachment_errors:
            failed_names = ", ".join(attachment_errors)
            attachment_feedback = (
                f"{attachment_line}\n"
                "⚠️ **Alguns anexos não entraram no GLPI desta vez.**\n"
                f"Arquivos pendentes: {failed_names}\n"
                "O chamado foi aberto normalmente e já registrei esse alerta para acompanhamento."
            )
        else:
            attachment_feedback = attachment_line
        ticket_link_line = f"🔗 **Acessar chamado:** {ticket_url}\n" if ticket_url else ""
        return (
            "🎉 **Chamado Aberto com Sucesso!**\n\n"
            "Sua solicitação já está com nossa equipe técnica.\n\n"
            f"🆔 **Ticket:** #{ticket_number}\n"
            f"📂 **Categoria:** {category}\n"
            f"🚦 **Prioridade:** {created_ticket['severity']}\n"
            f"{ticket_link_line}"
            f"{attachment_feedback}\n"
            "\n⏳ **Próximo passo:** Um técnico analisará seu caso e você receberá atualizações por aqui."
        )

    def _result(
        self,
        context: ConversationContext,
        bot_message: str,
        ticket_preview: dict | None = None,
        created_ticket: dict | None = None,
        bot_messages: list[str] | None = None,
    ) -> ConversationTurnResult:
        return ConversationTurnResult(
            session_id=context.session_id,
            bot_message=bot_message,
            state=context.state.value,
            bot_messages=bot_messages,
            ticket_preview=ticket_preview,
            created_ticket=created_ticket,
        )

    def _cancel_to_main_menu(
        self,
        context: ConversationContext,
        confirmation_message: str,
    ) -> ConversationTurnResult:
        main_menu = self._build_main_menu(context.user)
        return self._result(
            context,
            confirmation_message,
            bot_messages=[confirmation_message, main_menu],
        )
