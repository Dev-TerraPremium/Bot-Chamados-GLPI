import pytest

from app.authentication_and_identity.channel_identifier_normalizer import (
    ChannelIdentifierNormalizer,
)
from app.authentication_and_identity.channel_linking_factory import (
    InMemoryChannelIdentityLinkStore,
    MockChannelLinkAuditService,
)
from app.authentication_and_identity.channel_linking_service import ChannelLinkingService
from app.authentication_and_identity.document_partial_validator import (
    DocumentPartialValidator,
)
from app.authentication_and_identity.glpi_user_identity_lookup_service import (
    MockGLPIUserIdentityLookupService,
)


def test_normalize_phone():
    assert ChannelIdentifierNormalizer.normalize_phone("+55 (66) 99999-0980") == "66999990980"
    assert ChannelIdentifierNormalizer.normalize_phone("5511999999999") == "11999999999"
    assert ChannelIdentifierNormalizer.normalize_phone("(11) 9999-9999") == "1199999999"
    assert ChannelIdentifierNormalizer.normalize_phone("66999990980") == "66999990980"


def test_normalize_cpf():
    assert ChannelIdentifierNormalizer.normalize_cpf("099.150.671-51") == "09915067151"
    assert ChannelIdentifierNormalizer.normalize_cpf(" 123 . 456 - 78") == "12345678"
    assert ChannelIdentifierNormalizer.normalize_cpf("CPF: 099.150.671-51") == "09915067151"


def test_cpf_partial_validation_match():
    validator = DocumentPartialValidator(pepper="test", prefix_length=6)
    assert validator.compare_partial_with_full("099150", "09915067151") is True


def test_cpf_partial_validation_mismatch():
    validator = DocumentPartialValidator(pepper="test", prefix_length=6)
    assert validator.compare_partial_with_full("099151", "09915067151") is False


@pytest.fixture
def linking_service():
    return ChannelLinkingService(
        store=InMemoryChannelIdentityLinkStore(),
        audit_service=MockChannelLinkAuditService(),
        lookup_service=MockGLPIUserIdentityLookupService(),
        pepper="test_pepper",
        prefix_length=6,
        max_attempts=3,
        allow_web_simulator_auto_user=False,
    )


def test_link_success_flow(linking_service):
    res = linking_service.resolve_or_handle("whatsapp", "66999990980", "Oi")
    assert not res.is_linked
    assert res.requires_user_action
    assert "6 primeiros dígitos" in res.bot_message.lower()

    res2 = linking_service.resolve_or_handle("whatsapp", "66999990980", "099150")
    assert not res2.is_linked
    assert res2.requires_user_action
    assert "vínculo criado com sucesso" in res2.bot_message.lower()

    res3 = linking_service.resolve_or_handle("whatsapp", "66999990980", "Oi")
    assert res3.is_linked
    assert not res3.requires_user_action
    assert res3.user is not None
    assert res3.user.glpi_user_id == 266


def test_link_success_ignores_channel_phone_when_cpf_prefix_matches(linking_service):
    linking_service.resolve_or_handle("whatsapp", "66000000000", "Oi")

    res = linking_service.resolve_or_handle("whatsapp", "66000000000", "099150")

    assert "vínculo criado com sucesso" in res.bot_message.lower()
    linked = linking_service.resolve_or_handle("whatsapp", "66000000000", "Oi")
    assert linked.is_linked
    assert linked.user is not None
    assert linked.user.glpi_user_id == 266


def test_link_ambiguity_flow(linking_service):
    res = linking_service.resolve_or_handle("whatsapp", "66988887777", "Oi")
    assert not res.is_linked

    res2 = linking_service.resolve_or_handle("whatsapp", "66988887777", "123456")
    assert not res2.is_linked
    assert res2.is_blocked


def test_link_failure_and_block_flow(linking_service):
    linking_service.resolve_or_handle("whatsapp", "66999990980", "Oi")

    res = linking_service.resolve_or_handle("whatsapp", "66999990980", "999999")
    assert "não consegui confirmar" in res.bot_message.lower()

    res = linking_service.resolve_or_handle("whatsapp", "66999990980", "888888")
    assert "não consegui confirmar" in res.bot_message.lower()

    res = linking_service.resolve_or_handle("whatsapp", "66999990980", "777777")
    assert "bloqueado por segurança" in res.bot_message.lower()
    assert res.is_blocked

    res = linking_service.resolve_or_handle("whatsapp", "66999990980", "099150")
    assert "bloqueado por segurança" in res.bot_message.lower()


def test_teams_linking_uses_channel_identifier_without_phone_normalization(linking_service):
    res = linking_service.resolve_or_handle("teams", "29:teams-user-id", "Oi")
    assert not res.is_linked
    assert res.requires_user_action
    assert "microsoft teams" in res.bot_message.lower()

    res2 = linking_service.resolve_or_handle("teams", "29:teams-user-id", "099150")
    assert not res2.is_linked
    assert "vínculo criado com sucesso" in res2.bot_message.lower()

    res3 = linking_service.resolve_or_handle("teams", "29:teams-user-id", "Oi")
    assert res3.is_linked
    assert res3.user is not None
    assert res3.user.glpi_user_id == 266
