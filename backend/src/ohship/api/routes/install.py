"""Serve the agent install script at GET /install."""

from importlib.resources import files

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse

from ohship.config import settings
from ohship.constants import PUBLIC_INSTALL_URL

router = APIRouter(tags=["install"])


@router.get("/install", include_in_schema=False)
def install_agent_script() -> PlainTextResponse:
    """One-liner bootstrap: curl -fsSL https://ohship.depak.dev/install | bash"""
    template = files("ohship.agent.templates").joinpath("install-agent.sh").read_text(encoding="utf-8")
    api_url = settings.api_url.rstrip("/")
    install_url = settings.install_url.rstrip("/")
    body = template.replace("__OHSHIP_DEFAULT_API_URL__", api_url)
    body = body.replace("__OHSHIP_INSTALL_URL__", install_url)
    return PlainTextResponse(body, media_type="text/plain; charset=utf-8")
