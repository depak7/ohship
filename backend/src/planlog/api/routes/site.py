"""Public marketing homepage at GET / (planlog.depak.dev)."""

from importlib.resources import files

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from planlog.config import settings

router = APIRouter(tags=["site"])


@router.get("/", include_in_schema=False)
def landing_page() -> HTMLResponse:
    html = files("planlog.agent.templates").joinpath("landing.html").read_text(encoding="utf-8")
    api = settings.api_url.rstrip("/")
    install = settings.install_url.rstrip("/")
    html = html.replace("__FRONTEND_URL__", settings.frontend_url.rstrip("/"))
    html = html.replace("__INSTALL_URL__", install)
    html = html.replace("__MCP_URL__", f"{api}/mcp")
    return HTMLResponse(html)
