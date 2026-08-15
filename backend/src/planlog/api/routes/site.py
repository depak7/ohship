"""Public marketing homepage at GET / (planlog.depak.dev)."""

from importlib.resources import files

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from planlog.config import settings
from planlog.constants import PUBLIC_REPO_URL

router = APIRouter(tags=["site"])


@router.get("/", include_in_schema=False)
def landing_page() -> HTMLResponse:
    html = files("planlog.agent.templates").joinpath("landing.html").read_text(encoding="utf-8")
    api = settings.api_url.rstrip("/")
    install = settings.install_url.rstrip("/")
    for placeholder, value in (
        ("__FRONTEND_URL__", settings.frontend_url.rstrip("/")),
        ("__INSTALL_URL__", install),
        ("__MCP_URL__", f"{api}/mcp"),
        ("__REPO_URL__", PUBLIC_REPO_URL),
        ("__SITE_URL__", install.removesuffix("/install") or api),
    ):
        html = html.replace(placeholder, value)
    return HTMLResponse(html)
