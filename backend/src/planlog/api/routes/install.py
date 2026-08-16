"""Serve the agent install script at GET /install."""

from importlib.resources import files

from fastapi import APIRouter, Request
from fastapi.responses import PlainTextResponse

from planlog import analytics
from planlog.config import settings
from planlog.constants import PUBLIC_INSTALL_URL

router = APIRouter(tags=["install"])


@router.get("/install", include_in_schema=False)
def install_agent_script(request: Request) -> PlainTextResponse:
    """One-liner bootstrap: curl -fsSL https://planlog.depak.dev/install | bash"""
    # Highest-signal event in the funnel and invisible to any browser script — a shell is
    # fetching a text file. `client` separates real installs from the crawlers that hit this
    # the moment the URL is posted anywhere.
    analytics.track("install-fetched", request=request)
    template = files("planlog.agent.templates").joinpath("install-agent.sh").read_text(encoding="utf-8")
    api_url = settings.api_url.rstrip("/")
    install_url = settings.install_url.rstrip("/")
    body = template.replace("__PLANLOG_DEFAULT_API_URL__", api_url)
    body = body.replace("__PLANLOG_INSTALL_URL__", install_url)
    return PlainTextResponse(body, media_type="text/plain; charset=utf-8")
