from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException, Request

from app.api_http_routes.conversation_routes import flow_controller
from app.application_config.settings import load_settings
from app.microsoft_teams.auth import TeamsBotFrameworkAuthenticator
from app.microsoft_teams.factory import build_teams_adapter


router = APIRouter(prefix="/api/teams", tags=["microsoft-teams"])


@router.post("/messages")
async def receive_teams_activity(
    request: Request,
    authorization: str | None = Header(default=None),
) -> dict:
    settings = load_settings()
    if not settings.teams_enabled:
        raise HTTPException(status_code=404, detail="teams_disabled")

    TeamsBotFrameworkAuthenticator(settings).validate_authorization_header(authorization)
    activity = await request.json()
    adapter = build_teams_adapter(settings, flow_controller)
    return adapter.receive_activity(activity)
