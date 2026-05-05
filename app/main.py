from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api_http_routes import (
    conversation_routes,
    healthcheck_routes,
    web_simulator_routes,
)
from app.application_config.logging_config import configure_logging
from app.application_config.settings import load_settings


configure_logging()
settings = load_settings()

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="MVP local on-premise para triagem simulada de chamados de TI.",
)

static_web_dir = Path(__file__).resolve().parents[1] / "static_web_simulator"
app.mount(
    "/static",
    StaticFiles(directory=static_web_dir),
    name="static",
)

app.include_router(web_simulator_routes.router)
app.include_router(healthcheck_routes.router)
app.include_router(conversation_routes.router)
if settings.expose_debug_routes:
    app.include_router(conversation_routes.debug_router)
