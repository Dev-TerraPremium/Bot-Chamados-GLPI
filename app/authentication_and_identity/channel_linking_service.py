from dataclasses import dataclass
import datetime
import re

from app.authentication_and_identity.channel_identity_link_model import ChannelIdentityLink, ChannelIdentityLinkStatus
from app.authentication_and_identity.channel_identity_link_store_interface import ChannelIdentityLinkStoreInterface
from app.authentication_and_identity.channel_link_audit_service import ChannelLinkAuditService
from app.authentication_and_identity.channel_identifier_normalizer import ChannelIdentifierNormalizer
from app.authentication_and_identity.document_partial_validator import DocumentPartialValidator
from app.authentication_and_identity.glpi_user_identity_lookup_service import GLPIUserIdentityLookupServiceInterface
from app.authentication_and_identity.authenticated_user_model import AuthenticatedUser

@dataclass
class ChannelAuthResolution:
    is_linked: bool
    user: AuthenticatedUser | None
    requires_user_action: bool
    bot_message: str | None
    is_blocked: bool = False

class ChannelLinkingService:
    def __init__(
        self,
        store: ChannelIdentityLinkStoreInterface,
        audit_service: ChannelLinkAuditService,
        lookup_service: GLPIUserIdentityLookupServiceInterface,
        pepper: str,
        prefix_length: int = 4,
        max_attempts: int = 3,
        allow_web_simulator_auto_user: bool = False,
    ):
        self.store = store
        self.audit_service = audit_service
        self.lookup_service = lookup_service
        self.validator = DocumentPartialValidator(pepper=pepper, prefix_length=prefix_length)
        self.prefix_length = prefix_length
        self.max_attempts = max_attempts
        self.allow_web_simulator_auto_user = allow_web_simulator_auto_user

    def resolve_or_handle(self, channel: str, channel_identifier: str, message: str) -> ChannelAuthResolution:
        # 1. Normalization
        if channel == "web_simulator" and not channel_identifier:
            channel_identifier = "66999990980"  # default mock phone

        normalized_id = ChannelIdentifierNormalizer.normalize_phone(channel_identifier)
        masked_id = ChannelIdentifierNormalizer.mask_phone(normalized_id)
        
        # Web Simulator override
        if channel == "web_simulator" and self.allow_web_simulator_auto_user:
            return ChannelAuthResolution(
                is_linked=True,
                user=AuthenticatedUser(
                    full_name="Pedro Torres (Simulador)",
                    login="pedro.torres",
                    email="pedro.torres@terrapremium.com.br",
                    glpi_user_id=266
                ),
                requires_user_action=False,
                bot_message=None
            )

        link = self.store.get(channel, normalized_id)
        
        # Case: Blocked
        if link and link.status == ChannelIdentityLinkStatus.BLOCKED:
            return ChannelAuthResolution(
                is_linked=False,
                user=None,
                requires_user_action=True,
                bot_message="🚫 Este canal foi bloqueado por segurança. Procure o TI para desbloqueio.",
                is_blocked=True
            )
            
        # Case: Active
        if link and link.status == ChannelIdentityLinkStatus.ACTIVE:
            user = AuthenticatedUser(
                full_name=link.display_name or "Usuário",
                login=link.glpi_login or "login",
                email=link.email or "",
                glpi_user_id=link.glpi_user_id or 0
            )
            return ChannelAuthResolution(
                is_linked=True,
                user=user,
                requires_user_action=False,
                bot_message=None
            )

        # Case: Pending -> check message for CPF
        if link and link.status == ChannelIdentityLinkStatus.PENDING:
            return self._handle_pending_cpf(link, message, masked_id)

        # Case: No link -> create pending and ask
        return self._start_linking_process(channel, normalized_id, masked_id)

    def _start_linking_process(self, channel: str, normalized_id: str, masked_id: str) -> ChannelAuthResolution:
        link = ChannelIdentityLink(
            channel=channel,
            channel_identifier=normalized_id,
            status=ChannelIdentityLinkStatus.PENDING
        )
        self.store.save(link)
        self.audit_service.log_link_attempt(channel, masked_id)
        
        return ChannelAuthResolution(
            is_linked=False,
            user=None,
            requires_user_action=True,
            bot_message=(
                "🔐 **Segurança e Identificação**\n\n"
                "Olá! Para começarmos, preciso vincular este número de WhatsApp ao seu perfil no sistema de chamados.\n\n"
                f"Identifiquei o telefone com final **{normalized_id[-4:]}**.\n\n"
                f"Por favor, digite apenas os **{self.prefix_length} primeiros dígitos** do seu CPF para confirmar sua identidade:"
            )
        )

    def _handle_pending_cpf(self, link: ChannelIdentityLink, message: str, masked_id: str) -> ChannelAuthResolution:
        cpf_prefix = ChannelIdentifierNormalizer.normalize_cpf(message)
        
        # If input doesn't look like digits at all, warn
        if not re.match(r"^\d+$", cpf_prefix):
            return ChannelAuthResolution(
                is_linked=False,
                user=None,
                requires_user_action=True,
                bot_message=f"⚠️ Por favor, informe apenas números (os {self.prefix_length} primeiros dígitos do CPF)."
            )

        # If they gave too few digits
        if len(cpf_prefix) < self.prefix_length:
            return ChannelAuthResolution(
                is_linked=False,
                user=None,
                requires_user_action=True,
                bot_message=f"⚠️ Você informou menos de {self.prefix_length} dígitos. Informe os **{self.prefix_length} primeiros dígitos** do seu CPF."
            )

        cpf_prefix = cpf_prefix[:self.prefix_length]
        
        candidates = self.lookup_service.find_active_candidates_by_channel_phone_and_cpf_prefix(
            link.channel_identifier, cpf_prefix
        )
        
        if len(candidates) == 1:
            user_data = candidates[0]
            link.status = ChannelIdentityLinkStatus.ACTIVE
            link.glpi_user_id = user_data.id
            link.glpi_login = user_data.name
            link.display_name = user_data.firstname or user_data.realname or user_data.name
            link.email = user_data.email
            link.cpf_partial_hmac = self.validator.hash_partial_cpf(cpf_prefix)
            link.verified_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
            link.updated_at = link.verified_at
            
            self.store.save(link)
            self.audit_service.log_link_created(link.channel, masked_id, link.glpi_user_id)
            
            return ChannelAuthResolution(
                is_linked=False, # Just linked, we send the welcome message
                user=None,
                requires_user_action=True,
                bot_message=f"✅ Vínculo criado com sucesso. Olá, {link.display_name}. Você já pode abrir e consultar seus chamados.\n\nEnvie qualquer mensagem para ver o menu principal."
            )
            
        elif len(candidates) > 1:
            link.status = ChannelIdentityLinkStatus.BLOCKED
            link.unlock_required = True
            link.updated_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
            self.store.save(link)
            
            self.audit_service.log_ambiguity(link.channel, masked_id, len(candidates))
            
            return ChannelAuthResolution(
                is_linked=False,
                user=None,
                requires_user_action=True,
                bot_message="🚫 Encontrei mais de um cadastro possível. Por segurança, procure o TI para liberação.",
                is_blocked=True
            )
            
        else:
            link.failed_attempts += 1
            link.updated_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
            
            if link.failed_attempts >= self.max_attempts:
                link.status = ChannelIdentityLinkStatus.BLOCKED
                link.unlock_required = True
                self.store.save(link)
                self.audit_service.log_channel_blocked(link.channel, masked_id)
                return ChannelAuthResolution(
                    is_linked=False,
                    user=None,
                    requires_user_action=True,
                    bot_message="🚫 Este canal foi bloqueado por segurança. Procure o TI para desbloqueio.",
                    is_blocked=True
                )
            
            self.store.save(link)
            self.audit_service.log_cpf_failure(link.channel, masked_id, link.failed_attempts)
            
            return ChannelAuthResolution(
                is_linked=False,
                user=None,
                requires_user_action=True,
                bot_message="❌ Não consegui confirmar seus dados. Verifique os dígitos informados e tente novamente ou procure o TI."
            )

