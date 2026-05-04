from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse


router = APIRouter(tags=["web-simulator"])

STATIC_WEB_DIR = Path(__file__).resolve().parents[2] / "static_web_simulator"


@router.get("/")
def serve_web_simulator() -> FileResponse:
    return FileResponse(STATIC_WEB_DIR / "index.html")

