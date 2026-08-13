"""MCP TokenVerifier — validates Planlog JWTs (and API keys for compatibility)."""

from mcp.server.auth.provider import AccessToken, TokenVerifier

from planlog.auth import try_decode_access_token
from planlog.db import engine
from planlog.oauth.provider import MCP_SCOPE, oauth_provider
from sqlmodel import Session


class PlanlogTokenVerifier(TokenVerifier):
    async def verify_token(self, token: str) -> AccessToken | None:
        # Prefer provider cache / JWT decode
        access = await oauth_provider.load_access_token(token)
        if access:
            return access

        user_id = try_decode_access_token(token)
        if user_id:
            return AccessToken(
                token=token,
                client_id="planlog",
                scopes=[MCP_SCOPE],
                subject=str(user_id),
                claims={"user_id": str(user_id)},
            )

        # Allow MCP API keys (os_... / legacy dl_...) for agents that prefer keys
        if token.startswith(("os_", "dl_")):
            from planlog.auth import get_user_by_api_key

            with Session(engine) as session:
                user = get_user_by_api_key(session, token)
                if not user:
                    return None
                return AccessToken(
                    token=token,
                    client_id="api-key",
                    scopes=[MCP_SCOPE],
                    subject=str(user.id),
                    claims={"user_id": str(user.id), "auth": "api_key"},
                )
        return None
