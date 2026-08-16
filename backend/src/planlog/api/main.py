import logging
import os
from contextlib import asynccontextmanager
from urllib.parse import urlparse

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import AnyHttpUrl
from starlette.middleware.authentication import AuthenticationMiddleware

from mcp.server.auth.middleware.auth_context import AuthContextMiddleware
from mcp.server.auth.middleware.bearer_auth import BearerAuthBackend
from mcp.server.auth.routes import create_auth_routes
from mcp.server.auth.settings import ClientRegistrationOptions

from planlog import analytics
from planlog.api.routes import auth, install, oauth, orgs, plans, public, site
from planlog.config import settings
from planlog.db import check_db_connection
from planlog.mcp.server import create_mcp_server, mcp_transport_security
from planlog.oauth.provider import MCP_SCOPE, oauth_provider
from planlog.oauth.token_verifier import PlanlogTokenVerifier

logger = logging.getLogger(__name__)

# MCP resource server (Streamable HTTP + OAuth token verification)
mcp_http = create_mcp_server(enable_oauth=True)


def _warn_if_multi_worker() -> None:
    """MCP sessions are per-process, so more than one worker silently breaks /mcp.

    StreamableHTTPSessionManager holds live sessions in an in-process dict. Spread requests
    across workers and `initialize` lands on one while `tools/list` lands on another, which
    answers "Session not found" — with no teardown log, because the session is alive in the
    other process. Heroku's buildpack sets WEB_CONCURRENCY and uvicorn honours it unless
    --workers is passed, so this is easy to reintroduce by deleting one Procfile flag.
    """
    try:
        concurrency = int(os.environ.get("WEB_CONCURRENCY", "1"))
    except ValueError:
        return
    if concurrency > 1:
        logger.warning(
            "WEB_CONCURRENCY=%s but MCP Streamable HTTP keeps sessions in-process. "
            "Unless the server runs with --workers 1, /mcp will intermittently return "
            "'Session not found' and clients will report 'Not connected'.",
            concurrency,
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    _warn_if_multi_worker()
    async with analytics.lifespan(), mcp_http.session_manager.run():
        yield


app = FastAPI(title="Planlog API", version="0.1.0", lifespan=lifespan)

# The MCP auth stack: RequireAuthMiddleware rides along on the /mcp route we copy
# below, but these two live on the sub-app's middleware list, which copying routes
# drops. AuthenticationMiddleware populates scope["user"] (without it /mcp 401s on
# every request); AuthContextMiddleware exposes the token to get_access_token().
# Added first so CORS below ends up outermost.
app.add_middleware(AuthContextMiddleware)
app.add_middleware(
    AuthenticationMiddleware,
    backend=BearerAuthBackend(PlanlogTokenVerifier()),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict:
    db_ok = check_db_connection()
    return {
        "status": "ok" if db_ok else "degraded",
        "database": "connected" if db_ok else "unavailable",
        "mcp": f"{settings.api_url.rstrip('/')}/mcp",
        "oauth": True,
    }


app.mount("/static", StaticFiles(directory=site.STATIC_DIR), name="static")
app.include_router(site.router)
app.include_router(install.router)
app.include_router(auth.router, prefix="/api/v1")
app.include_router(orgs.router, prefix="/api/v1")
app.include_router(plans.router, prefix="/api/v1")
app.include_router(public.router, prefix="/api/v1")
app.include_router(oauth.router, prefix="/api/v1")

# OAuth Authorization Server routes (discovery, register, authorize, token)
issuer = AnyHttpUrl(settings.api_url.rstrip("/") + "/")
for route in create_auth_routes(
    provider=oauth_provider,
    issuer_url=issuer,
    client_registration_options=ClientRegistrationOptions(
        enabled=True,
        valid_scopes=[MCP_SCOPE],
        default_scopes=[MCP_SCOPE],
    ),
):
    app.routes.append(route)

# Streamable HTTP MCP routes: /mcp + /.well-known/oauth-protected-resource/mcp
_mcp_host = urlparse(settings.api_url).hostname or "0.0.0.0"
for route in mcp_http.streamable_http_app(
    transport_security=mcp_transport_security(),
    host=_mcp_host,
).routes:
    app.routes.append(route)
