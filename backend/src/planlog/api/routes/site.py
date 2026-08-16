"""Public marketing homepage at GET / (planlog.depak.dev)."""

from importlib.resources import files
from urllib.parse import urlparse

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from planlog.config import settings
from planlog.constants import PUBLIC_REPO_URL

router = APIRouter(tags=["site"])


def _analytics_snippet() -> str:
    """Umami tracker, or nothing at all when unconfigured.

    data-domains covers both hosts so the landing page and the app stay one funnel — Umami is
    cookieless (session = hash of IP + UA + website), so crossing subdomains needs no cookie.
    """
    website_id = settings.umami_website_id
    if not website_id:
        return ""
    host = settings.umami_host.rstrip("/")
    app_host = urlparse(settings.frontend_url).hostname or ""
    site_host = urlparse(settings.api_url).hostname or ""
    domains = ",".join(d for d in dict.fromkeys([site_host, app_host]) if d)
    return (
        f'<script defer src="{host}/script.js" data-website-id="{website_id}"'
        f' data-domains="{domains}"></script>'
    )


@router.get("/", include_in_schema=False)
def landing_page() -> HTMLResponse:
    html = files("planlog.agent.templates").joinpath("landing.html").read_text(encoding="utf-8")
    api = settings.api_url.rstrip("/")
    install = settings.install_url.rstrip("/")
    for placeholder, value in (
        ("__ANALYTICS_SNIPPET__", _analytics_snippet()),
        ("__FRONTEND_URL__", settings.frontend_url.rstrip("/")),
        ("__INSTALL_URL__", install),
        ("__MCP_URL__", f"{api}/mcp"),
        ("__REPO_URL__", PUBLIC_REPO_URL),
        ("__SITE_URL__", install.removesuffix("/install") or api),
    ):
        html = html.replace(placeholder, value)
    return HTMLResponse(html)
