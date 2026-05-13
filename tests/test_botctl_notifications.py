import importlib.util
from pathlib import Path


def load_botctl_module():
    module_path = Path(__file__).resolve().parents[1] / "scripts" / "botctl.py"
    spec = importlib.util.spec_from_file_location("botctl_for_tests", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_notification_diagnostics_flags_missing_enabled_env_as_disabled():
    botctl = load_botctl_module()

    rows = botctl.notification_diagnostics({"STATE_BACKEND": "redis"})

    assert rows == [
        [
            "Notificacoes GLPI",
            "disabled",
            "TICKET_NOTIFICATIONS_ENABLED ausente; padrao da aplicacao e false",
        ]
    ]


def test_notification_diagnostics_requires_token_and_scheduler_when_enabled():
    botctl = load_botctl_module()
    env = {
        "TICKET_NOTIFICATIONS_ENABLED": "true",
        "STATE_BACKEND": "redis",
        "USE_CELERY_WORKERS": "true",
        "GLPI_INTEGRATION_MODE": "real",
    }

    rows = botctl.notification_diagnostics(env, containers=[])

    assert rows[0][1] == "degraded"
    assert "WHATSAPP_INTERNAL_API_TOKEN ausente" in rows[0][2]
    assert "container scheduler nao esta running" in rows[0][2]


def test_notification_diagnostics_reports_ok_with_required_runtime_parts():
    botctl = load_botctl_module()
    env = {
        "TICKET_NOTIFICATIONS_ENABLED": "true",
        "TICKET_NOTIFICATION_POLL_INTERVAL_SECONDS": "15",
        "STATE_BACKEND": "redis",
        "USE_CELERY_WORKERS": "true",
        "GLPI_INTEGRATION_MODE": "real",
        "WHATSAPP_INTERNAL_API_TOKEN": "secret",
    }
    containers = [{"Service": "scheduler", "State": "running"}]

    rows = botctl.notification_diagnostics(env, containers=containers)

    assert rows == [["Notificacoes GLPI", "ok", "poll ativo a cada 15s"]]
