from dataclasses import dataclass
from typing import Protocol

@dataclass(slots=True)
class GLPIUserIdentity:
    id: int
    name: str
    firstname: str
    realname: str
    email: str
    phone: str
    phone2: str
    mobile: str
    registration_number: str
    is_active: bool

class GLPIUserIdentityLookupServiceInterface(Protocol):
    def find_active_candidates_by_channel_phone_and_cpf_prefix(
        self, phone: str, cpf_prefix: str
    ) -> list[GLPIUserIdentity]:
        ...

class MockGLPIUserIdentityLookupService(GLPIUserIdentityLookupServiceInterface):
    """
    Mock implementation for local testing.
    """
    def __init__(self):
        self.mock_users = [
            GLPIUserIdentity(
                id=266,
                name="pedro.torres",
                firstname="Pedro",
                realname="Pedro Américo Paletot de Alcântara Torres",
                email="pedro.torres@terrapremium.com.br",
                phone="",
                phone2="",
                mobile="66999990980",
                registration_number="099.150.671-51",
                is_active=True
            ),
            GLPIUserIdentity(
                id=300,
                name="joao.silva",
                firstname="Joao",
                realname="Joao da Silva",
                email="joao.silva@empresa.local",
                phone="66988887777",
                phone2="",
                mobile="",
                registration_number="12345678901",
                is_active=True
            ),
            # Duplicated phone for ambiguity test
            GLPIUserIdentity(
                id=301,
                name="maria.souza",
                firstname="Maria",
                realname="Maria Souza",
                email="maria.souza@empresa.local",
                phone="66988887777",
                phone2="",
                mobile="",
                registration_number="12399999999",
                is_active=True
            )
        ]

    def find_active_candidates_by_channel_phone_and_cpf_prefix(
        self, phone: str, cpf_prefix: str
    ) -> list[GLPIUserIdentity]:
        
        from app.authentication_and_identity.channel_identifier_normalizer import ChannelIdentifierNormalizer
        from app.authentication_and_identity.document_partial_validator import DocumentPartialValidator
        
        candidates = []
        validator = DocumentPartialValidator(pepper="", prefix_length=len(cpf_prefix))
        
        for u in self.mock_users:
            if not u.is_active:
                continue
                
            phones = [
                ChannelIdentifierNormalizer.normalize_phone(u.phone),
                ChannelIdentifierNormalizer.normalize_phone(u.phone2),
                ChannelIdentifierNormalizer.normalize_phone(u.mobile)
            ]
            
            if phone in phones:
                full_cpf = ChannelIdentifierNormalizer.normalize_cpf(u.registration_number)
                if validator.compare_partial_with_full(cpf_prefix, full_cpf):
                    candidates.append(u)
                    
        return candidates
