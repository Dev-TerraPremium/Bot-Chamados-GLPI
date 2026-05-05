from app.application_config.settings import AppSettings
from app.background_jobs.celery_description_organizer import CeleryDescriptionOrganizer
from app.background_jobs.celery_glpi_client import CeleryGLPIClient
from app.background_jobs.tasks import create_glpi_ticket_task, organize_description_task


def test_celery_description_organizer_uses_configured_queue(monkeypatch) -> None:
    class FakeAsyncResult:
        def get(self, timeout: int, disable_sync_subtasks: bool):
            return {
                "status": "organized",
                "organized_text": "Texto organizado.",
                "clarification_question": "",
                "confidence": 0.9,
                "backend": "fake",
            }

    captured = {}

    def fake_apply_async(args, queue):
        captured["args"] = args
        captured["queue"] = queue
        return FakeAsyncResult()

    monkeypatch.setattr(organize_description_task, "apply_async", fake_apply_async)

    organizer = CeleryDescriptionOrganizer(
        AppSettings(use_celery_workers=True, ai_queue_name="ai_local")
    )
    result = organizer.organize_ticket_description("texto", None, "descricao")

    assert result.organized_text == "Texto organizado."
    assert captured["queue"] == "ai_local"


def test_celery_glpi_client_uses_configured_queue(monkeypatch) -> None:
    class FakeAsyncResult:
        def get(self, timeout: int, disable_sync_subtasks: bool):
            return {
                "ticket_number": 10001,
                "title": "Teste",
                "status": "Aberto",
                "severity": "Alta",
                "description": "Descricao",
                "category_name": "GLPI",
                "requester_login": "pedro.torres",
                "glpi_user_id": 266,
                "channel": "web_simulator",
                "location": "TI",
                "impact_label": "Impacto",
                "evidence": "Não informado",
                "opening_mode": "Abertura assistida",
                "created_at": "2026-05-05T00:00:00Z",
                "followups": [],
            }

    captured = {}

    def fake_apply_async(args, queue):
        captured["args"] = args
        captured["queue"] = queue
        return FakeAsyncResult()

    monkeypatch.setattr(create_glpi_ticket_task, "apply_async", fake_apply_async)

    client = CeleryGLPIClient(
        AppSettings(use_celery_workers=True, glpi_queue_name="glpi_io")
    )
    ticket = client.create_ticket({"glpi_input": {}})

    assert ticket.ticket_number == 10001
    assert captured["queue"] == "glpi_io"
