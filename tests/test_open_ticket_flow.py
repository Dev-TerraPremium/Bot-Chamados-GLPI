from uuid import uuid4

from app.application_config.settings import AppSettings
from app.background_jobs.tasks import (
    create_glpi_ticket_task,
    organize_description_task,
    worker_ticket_store,
)
from app.conversation_engine.conversation_flow_controller import (
    ConversationFlowController,
)
from app.local_light_ai.description_organization_models import (
    DescriptionOrganizationResult,
)
from app.glpi_integration_reserved.glpi_category_catalog_service import GLPICategoryOption
from app.glpi_integration_reserved.glpi_future_real_client import GLPIClientError
from app.glpi_integration_reserved.glpi_location_catalog_service import GLPILocationOption
from app.ticket_domain.ticket_models import TicketCreated


class FakeDescriptionOrganizer:
    def __init__(self, organized_text: str) -> None:
        self.organized_text = organized_text

    def organize_ticket_description(
        self,
        user_text: str,
        category_name: str | None = None,
        purpose: str = "descricao_chamado",
    ) -> DescriptionOrganizationResult:
        return DescriptionOrganizationResult(
            status="organized",
            organized_text=self.organized_text,
            clarification_question="",
            confidence=0.9,
            backend="fake-generative",
        )


class FakeRealCatalog:
    category = GLPICategoryOption(
        id=544,
        name="WI-FI",
        complete_name="INFRAESTRUTURA > REDES > WI-FI",
        entity_id=3,
        parent_id=528,
        level=3,
    )

    def get_categories(self, ticket_type=None):
        return [self.category]

    def get_by_id(self, category_id: int):
        return self.category if category_id == 544 else None

    def search(self, query: str, *, ticket_type=None, limit: int = 5):
        return [self.category]


class FakeRealCategorySuggester:
    def find_best_match(self, text: str, *, ticket_type=None):
        from app.triage_rules.category_matching_service import CategoryMatch

        return CategoryMatch(544, "INFRAESTRUTURA > REDES > WI-FI", 0.9, "fake")


class FakeLocationService:
    locations = [
        GLPILocationOption(1, "Matriz", "Matriz", 3),
        GLPILocationOption(91, "Rondonópolis", "Rondonópolis", 3),
    ]

    def get_locations(self):
        return self.locations.copy()

    def get_by_id(self, location_id: int):
        return next((item for item in self.locations if item.id == location_id), None)

    def search(self, query: str, *, limit: int = 5):
        query = query.casefold()
        matches = [
            item for item in self.locations if query in item.display_name.casefold()
        ]
        return matches[:limit]

    def get_user_default_location(self, user_id: int):
        return None


class FailingRealCatalog:
    def get_categories(self, ticket_type=None):
        raise GLPIClientError("GLPI recusou a operacao solicitada.")

    def get_by_id(self, category_id: int):
        raise GLPIClientError("GLPI recusou a operacao solicitada.")

    def search(self, query: str, *, ticket_type=None, limit: int = 5):
        raise GLPIClientError("GLPI recusou a operacao solicitada.")


class FailingRealCategorySuggester:
    def find_best_match(self, text: str, *, ticket_type=None):
        raise GLPIClientError("GLPI recusou a operacao solicitada.")


class FakeUsageTracker:
    def __init__(self):
        self.incremented = []

    def increment(self, category_id: int) -> None:
        self.incremented.append(category_id)

    def top_categories(self, catalog, *, ticket_type=None, limit: int = 5):
        return catalog.get_categories(ticket_type)[:limit]


class FakeRealGLPIClient:
    def __init__(self):
        self.payload = None

    def create_ticket(self, ticket_data: dict) -> TicketCreated:
        self.payload = ticket_data
        return TicketCreated(
            ticket_number=1234,
            title=ticket_data["title"],
            status="Aberto",
            severity=ticket_data["severity"],
            description=ticket_data["description"],
            category_name=ticket_data["category_name"],
            requester_login=ticket_data["requester_login"],
            glpi_user_id=ticket_data["glpi_user_id"],
            channel=ticket_data["channel"],
            location=ticket_data["location"],
            impact_label=ticket_data["impact_label"],
            evidence=ticket_data["evidence"],
            opening_mode=ticket_data["opening_mode"],
            created_at="2026-05-07T00:00:00Z",
            attachments_expected_count=len(ticket_data.get("attachments") or []),
            attachments_uploaded_count=len(ticket_data.get("attachments") or []),
        )


class FakeRealGLPIClientWithAttachmentFailure(FakeRealGLPIClient):
    def create_ticket(self, ticket_data: dict) -> TicketCreated:
        self.payload = ticket_data
        return TicketCreated(
            ticket_number=1234,
            title=ticket_data["title"],
            status="Aberto",
            severity=ticket_data["severity"],
            description=ticket_data["description"],
            category_name=ticket_data["category_name"],
            requester_login=ticket_data["requester_login"],
            glpi_user_id=ticket_data["glpi_user_id"],
            channel=ticket_data["channel"],
            location=ticket_data["location"],
            impact_label=ticket_data["impact_label"],
            evidence=ticket_data["evidence"],
            opening_mode=ticket_data["opening_mode"],
            created_at="2026-05-07T00:00:00Z",
            attachments_expected_count=len(ticket_data.get("attachments") or []),
            attachments_uploaded_count=0,
            attachment_errors=["erro.png"],
        )


def send(
    controller: ConversationFlowController,
    session_id: str,
    message: str,
    media: list[dict] | None = None,
) -> dict:
    result = controller.process_message(
        session_id=session_id,
        message=message,
        media=media,
    )
    return {
        "session_id": result.session_id,
        "bot_message": result.bot_message,
        "bot_messages": result.bot_messages,
        "state": result.state,
        "ticket_preview": result.ticket_preview,
        "created_ticket": result.created_ticket,
    }


def test_open_ticket_flow_uses_automatic_category_assignment() -> None:
    session_id = str(uuid4())
    controller = ConversationFlowController(
        settings=AppSettings(
            ai_guided_detailing_enabled=False,
            glpi_ticket_public_url_template="https://glpi.local/front/ticket.form.php?id={ticket_id}",
        ),
        description_organizer=FakeDescriptionOrganizer("Wi-Fi caindo no depósito.")
    )

    send(controller, session_id, "__start__")
    open_prompt = send(controller, session_id, "1")
    assert "Conte o que aconteceu" in open_prompt["bot_message"]

    impact_response = send(controller, session_id, "wifi caindo no deposito")
    assert impact_response["state"] == "impact_selection"
    assert "Revise o texto do chamado" not in impact_response["bot_message"]
    assert "Ubiquiti / Wi-Fi" not in impact_response["bot_message"]

    send(controller, session_id, "2")
    send(controller, session_id, "Matriz")
    summary_response = send(controller, session_id, "2")
    assert summary_response["ticket_preview"]["category"] == "Ubiquiti / Wi-Fi"
    assert "Posso abrir seu chamado agora?" in summary_response["bot_message"]
    assert "Revisão Final" not in summary_response["bot_message"]

    created_response = send(controller, session_id, "1")
    assert "Solicitação registrada com sucesso." in created_response["bot_message"]
    assert created_response["bot_messages"] is None
    assert (
        f"https://glpi.local/front/ticket.form.php?id={created_response['created_ticket']['ticket_number']}"
        in created_response["bot_message"]
    )
    assert created_response["created_ticket"]["status"] == "Aberto"
    assert created_response["created_ticket"]["category_name"] == "Ubiquiti / Wi-Fi"


def test_open_ticket_flow_skips_description_review_and_keeps_category_autonomous() -> None:
    session_id = str(uuid4())
    controller = ConversationFlowController(
        settings=AppSettings(ai_guided_detailing_enabled=False),
        description_organizer=FakeDescriptionOrganizer(
            "Estou com meu acesso à pasta RH bloqueado."
        )
    )

    send(controller, session_id, "__start__")
    send(controller, session_id, "1")
    impact_response = send(controller, session_id, "Estou com meu acesso a pasta RH bloqueado")
    assert impact_response["state"] == "impact_selection"
    assert "Revise o texto do chamado" not in impact_response["bot_message"]
    assert "Acesso / Senha" not in impact_response["bot_message"]

    invalid_response = send(controller, session_id, "9")
    assert invalid_response["state"] == "impact_selection"


def test_open_ticket_flow_uses_natural_final_summary_and_separate_cancel_messages() -> None:
    session_id = str(uuid4())
    controller = ConversationFlowController(
        settings=AppSettings(ai_guided_detailing_enabled=False),
        description_organizer=FakeDescriptionOrganizer("Wi-Fi caindo no depósito."),
    )

    send(controller, session_id, "__start__")
    send(controller, session_id, "1")
    send(controller, session_id, "wifi caindo no deposito")
    send(controller, session_id, "2")
    send(controller, session_id, "Matriz")
    summary_response = send(controller, session_id, "2")

    assert summary_response["state"] == "final_confirmation"
    assert "Posso abrir seu chamado agora?" in summary_response["bot_message"]
    assert "Revisão Final" not in summary_response["bot_message"]
    assert "Seu chamado será aberto na categoria" not in summary_response["bot_message"]
    assert "Categoria:" not in summary_response["bot_message"]
    assert "Resumo:" not in summary_response["bot_message"]

    cancel_response = send(controller, session_id, "2")

    assert cancel_response["state"] == "main_menu"
    assert cancel_response["bot_message"] == "❌ **Chamado cancelado com segurança.**"
    assert cancel_response["bot_messages"] is not None
    assert len(cancel_response["bot_messages"]) == 2


def test_open_ticket_flow_uses_celery_glpi_client_in_mock_mode(monkeypatch) -> None:
    class FakeDescriptionAsyncResult:
        def get(self, timeout: int, disable_sync_subtasks: bool):
            return {
                "status": "organized",
                "organized_text": "Wifi caindo no deposito.",
                "clarification_question": "",
                "confidence": 0.99,
                "backend": "mock-local-ai",
            }

    class FakeTicketAsyncResult:
        def get(self, timeout: int, disable_sync_subtasks: bool):
            return {
                "ticket_number": 10001,
                "title": "Wi-Fi",
                "status": "Aberto",
                "severity": "Média",
                "description": "Wifi caindo no deposito.",
                "category_name": "Ubiquiti / Wi-Fi",
                "requester_login": "pedro.torres",
                "glpi_user_id": 1001,
                "channel": "web_simulator",
                "location": "TI - Matriz",
                "impact_label": "Afeta somente a mim",
                "evidence": "Não informado",
                "opening_mode": "Abertura assistida",
                "created_at": "2026-05-05T00:00:00Z",
                "followups": [],
            }

    def fake_description_apply_async(args, queue):
        return FakeDescriptionAsyncResult()

    def fake_ticket_apply_async(args, queue):
        return FakeTicketAsyncResult()

    monkeypatch.setattr(
        organize_description_task, "apply_async", fake_description_apply_async
    )
    monkeypatch.setattr(create_glpi_ticket_task, "apply_async", fake_ticket_apply_async)
    worker_ticket_store.clear()
    session_id = str(uuid4())
    controller = ConversationFlowController(
        settings=AppSettings(
            use_celery_workers=True,
            state_backend="memory",
            glpi_integration_mode="mock",
            local_light_ai_mode="mock",
            ai_guided_detailing_enabled=False,
        )
    )

    send(controller, session_id, "__start__")
    send(controller, session_id, "1")
    send(controller, session_id, "wifi caindo no deposito")
    send(controller, session_id, "2")
    send(controller, session_id, "TI - Matriz")
    send(controller, session_id, "2")
    created_response = send(controller, session_id, "1")

    assert created_response["created_ticket"]["ticket_number"] == 10001
    assert "Solicitação registrada com sucesso." in created_response["bot_message"]
    assert created_response["bot_messages"] is None


def test_real_open_ticket_flow_uses_glpi_category_and_authenticated_requester() -> None:
    session_id = str(uuid4())
    glpi_client = FakeRealGLPIClient()
    usage_tracker = FakeUsageTracker()
    controller = ConversationFlowController(
        settings=AppSettings(
            glpi_integration_mode="real",
            glpi_base_url="https://glpi.local/apirest.php",
            glpi_app_token="app",
            glpi_user_token="user",
            glpi_default_entity_id=3,
            glpi_default_profile_id=4,
            glpi_default_requester_user_id=0,
            state_backend="memory",
            use_celery_workers=False,
            ai_guided_detailing_enabled=False,
        ),
        description_organizer=FakeDescriptionOrganizer("Wi-Fi caindo no depósito."),
        glpi_client=glpi_client,
        location_service=FakeLocationService(),
    )
    controller.category_catalog = FakeRealCatalog()
    controller.category_matching_service = FakeRealCategorySuggester()
    controller.category_usage_tracker = usage_tracker

    send(controller, session_id, "__start__")
    send(controller, session_id, "1")
    send(controller, session_id, "1")
    impact_response = send(controller, session_id, "wifi caindo no deposito")
    assert impact_response["state"] == "impact_selection"
    assert "Revise o texto do chamado" not in impact_response["bot_message"]
    assert "INFRAESTRUTURA > REDES > WI-FI" not in impact_response["bot_message"]

    send(controller, session_id, "2")
    send(controller, session_id, "Matriz")
    send(controller, session_id, "2")
    created_response = send(controller, session_id, "1")

    assert created_response["created_ticket"]["ticket_number"] == 1234
    assert glpi_client.payload["glpi_input"]["itilcategories_id"] == 544
    assert glpi_client.payload["glpi_input"]["locations_id"] == 1
    assert glpi_client.payload["glpi_input"]["_users_id_requester"] == 266
    assert usage_tracker.incremented == [544]


def test_real_open_ticket_flow_requires_valid_glpi_location() -> None:
    session_id = str(uuid4())
    glpi_client = FakeRealGLPIClient()
    controller = ConversationFlowController(
        settings=AppSettings(
            glpi_integration_mode="real",
            glpi_base_url="https://glpi.local/apirest.php",
            glpi_app_token="app",
            glpi_user_token="user",
            glpi_default_entity_id=3,
            glpi_default_profile_id=4,
            glpi_default_requester_user_id=0,
            state_backend="memory",
            use_celery_workers=False,
            ai_guided_detailing_enabled=False,
        ),
        description_organizer=FakeDescriptionOrganizer("Wi-Fi caindo no depósito."),
        glpi_client=glpi_client,
        location_service=FakeLocationService(),
    )
    controller.category_catalog = FakeRealCatalog()
    controller.category_matching_service = FakeRealCategorySuggester()
    controller.category_usage_tracker = FakeUsageTracker()

    send(controller, session_id, "__start__")
    send(controller, session_id, "1")
    send(controller, session_id, "1")
    send(controller, session_id, "wifi caindo no deposito")
    send(controller, session_id, "2")
    invalid_location = send(controller, session_id, "unidade inexistente")

    assert invalid_location["state"] == "location_collection"
    assert "Digite apenas" in invalid_location["bot_message"]


def test_real_open_ticket_flow_accepts_numbered_glpi_location_choice() -> None:
    session_id = str(uuid4())
    glpi_client = FakeRealGLPIClient()
    controller = ConversationFlowController(
        settings=AppSettings(
            glpi_integration_mode="real",
            glpi_base_url="https://glpi.local/apirest.php",
            glpi_app_token="app",
            glpi_user_token="user",
            glpi_default_entity_id=3,
            glpi_default_profile_id=4,
            glpi_default_requester_user_id=0,
            state_backend="memory",
            use_celery_workers=False,
            ai_guided_detailing_enabled=False,
        ),
        description_organizer=FakeDescriptionOrganizer("Mouse e teclado para compra."),
        glpi_client=glpi_client,
        location_service=FakeLocationService(),
    )
    controller.category_catalog = FakeRealCatalog()
    controller.category_matching_service = FakeRealCategorySuggester()
    controller.category_usage_tracker = FakeUsageTracker()

    send(controller, session_id, "__start__")
    send(controller, session_id, "1")
    send(controller, session_id, "1")
    send(controller, session_id, "Preciso de um mouse e teclado")
    location_prompt = send(controller, session_id, "1")
    assert location_prompt["state"] == "location_collection"
    assert "Digite apenas" in location_prompt["bot_message"]

    evidence_prompt = send(controller, session_id, "2")

    assert evidence_prompt["state"] == "evidence_decision"
    context = controller.conversation_store.get(session_id)
    assert context.location == "Rondonópolis"
    assert context.glpi_location_id == 91


def test_real_open_ticket_flow_collects_evidence_until_done_and_sends_attachment() -> None:
    session_id = str(uuid4())
    glpi_client = FakeRealGLPIClient()
    controller = ConversationFlowController(
        settings=AppSettings(
            glpi_integration_mode="real",
            glpi_base_url="https://glpi.local/apirest.php",
            glpi_app_token="app",
            glpi_user_token="user",
            glpi_default_entity_id=3,
            glpi_default_profile_id=4,
            glpi_default_requester_user_id=0,
            state_backend="memory",
            use_celery_workers=False,
            ai_guided_detailing_enabled=False,
        ),
        description_organizer=FakeDescriptionOrganizer("Evidência registrada."),
        glpi_client=glpi_client,
        location_service=FakeLocationService(),
    )
    controller.category_catalog = FakeRealCatalog()
    controller.category_matching_service = FakeRealCategorySuggester()
    controller.category_usage_tracker = FakeUsageTracker()

    send(controller, session_id, "__start__")
    send(controller, session_id, "1")
    send(controller, session_id, "1")
    send(controller, session_id, "wifi caindo no deposito")
    send(controller, session_id, "2")
    send(controller, session_id, "Matriz")
    evidence_prompt = send(controller, session_id, "1")
    assert "Espaço para Anexos" in evidence_prompt["bot_message"]

    evidence_response = send(
        controller,
        session_id,
        "segue o print do erro",
        media=[
            {
                "file_name": "erro.png",
                "mime_type": "image/png",
                "data_base64": "ZmFrZQ==",
            }
        ],
    )
    assert evidence_response["state"] == "evidence_collection"
    assert "Informação registrada" in evidence_response["bot_message"]

    summary_response = send(controller, session_id, "pronto")
    assert summary_response["state"] == "final_confirmation"

    created_response = send(controller, session_id, "1")
    assert created_response["created_ticket"]["attachments_expected_count"] == 1
    assert glpi_client.payload["attachments"] == [
        {
            "file_name": "erro.png",
            "mime_type": "image/png",
            "data_base64": "ZmFrZQ==",
        }
    ]


def test_real_open_ticket_flow_keeps_evidence_state_for_media_only_message() -> None:
    session_id = str(uuid4())
    glpi_client = FakeRealGLPIClient()
    controller = ConversationFlowController(
        settings=AppSettings(
            glpi_integration_mode="real",
            glpi_base_url="https://glpi.local/apirest.php",
            glpi_app_token="app",
            glpi_user_token="user",
            glpi_default_entity_id=3,
            glpi_default_profile_id=4,
            glpi_default_requester_user_id=0,
            state_backend="memory",
            use_celery_workers=False,
            ai_guided_detailing_enabled=False,
        ),
        description_organizer=FakeDescriptionOrganizer("Evidência registrada."),
        glpi_client=glpi_client,
        location_service=FakeLocationService(),
    )
    controller.category_catalog = FakeRealCatalog()
    controller.category_matching_service = FakeRealCategorySuggester()
    controller.category_usage_tracker = FakeUsageTracker()

    send(controller, session_id, "__start__")
    send(controller, session_id, "1")
    send(controller, session_id, "1")
    send(controller, session_id, "wifi caindo no deposito")
    send(controller, session_id, "2")
    send(controller, session_id, "Matriz")
    send(controller, session_id, "1")

    evidence_response = send(
        controller,
        session_id,
        "",
        media=[
            {
                "file_name": "erro.png",
                "mime_type": "image/png",
                "data_base64": "ZmFrZQ==",
            }
        ],
    )
    assert evidence_response["state"] == "evidence_collection"
    assert "Informação registrada" in evidence_response["bot_message"]
    assert "Abrir chamado" not in evidence_response["bot_message"]

    summary_response = send(controller, session_id, "pronto")
    assert summary_response["state"] == "final_confirmation"

    created_response = send(controller, session_id, "1")
    assert created_response["created_ticket"]["attachments_expected_count"] == 1
    assert created_response["created_ticket"]["attachments_uploaded_count"] == 1
    assert glpi_client.payload["evidence"] == "Anexos enviados pelo WhatsApp."


def test_real_open_ticket_flow_informs_when_glpi_attachment_link_fails() -> None:
    session_id = str(uuid4())
    glpi_client = FakeRealGLPIClientWithAttachmentFailure()
    controller = ConversationFlowController(
        settings=AppSettings(
            glpi_integration_mode="real",
            glpi_base_url="https://glpi.local/apirest.php",
            glpi_app_token="app",
            glpi_user_token="user",
            glpi_default_entity_id=3,
            glpi_default_profile_id=4,
            glpi_default_requester_user_id=0,
            state_backend="memory",
            use_celery_workers=False,
            ai_guided_detailing_enabled=False,
        ),
        description_organizer=FakeDescriptionOrganizer("Evidência registrada."),
        glpi_client=glpi_client,
        location_service=FakeLocationService(),
    )
    controller.category_catalog = FakeRealCatalog()
    controller.category_matching_service = FakeRealCategorySuggester()
    controller.category_usage_tracker = FakeUsageTracker()

    send(controller, session_id, "__start__")
    send(controller, session_id, "1")
    send(controller, session_id, "1")
    send(controller, session_id, "wifi caindo no deposito")
    send(controller, session_id, "2")
    send(controller, session_id, "Matriz")
    send(controller, session_id, "1")
    send(
        controller,
        session_id,
        "",
        media=[
            {
                "file_name": "erro.png",
                "mime_type": "image/png",
                "data_base64": "ZmFrZQ==",
            }
        ],
    )
    send(controller, session_id, "pronto")

    created_response = send(controller, session_id, "1")
    assert "Solicitação registrada com sucesso." in created_response["bot_message"]
    assert "Alguns anexos não foram enviados ao GLPI" in created_response["bot_message"]
    assert "erro.png" not in created_response["bot_message"]
