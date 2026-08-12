from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import AnyHttpUrl

from mcp.server.auth.routes import create_auth_routes
from mcp.server.auth.settings import ClientRegistrationOptions

from ohship.api.routes import auth, oauth, orgs, plans
from ohship.config import settings
from ohship.db import check_db_connection
from ohship.mcp.server import create_mcp_server
from ohship.oauth.provider import MCP_SCOPE, oauth_provider

# MCP resource server (Streamable HTTP + OAuth token verification)
mcp_http = create_mcp_server(enable_oauth=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with mcp_http.session_manager.run():
        yield


app = FastAPI(title="OhShip API", version="0.1.0", lifespan=lifespan)

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


app.include_router(auth.router, prefix="/api/v1")
app.include_router(orgs.router, prefix="/api/v1")
app.include_router(plans.router, prefix="/api/v1")
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
for route in mcp_http.streamable_http_app().routes:
    app.routes.append(route)
