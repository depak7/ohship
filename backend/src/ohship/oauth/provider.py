"""MCP OAuth Authorization Server — reuses OhShip email/Google login."""

from __future__ import annotations

import secrets
import time
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from pydantic import AnyHttpUrl, AnyUrl

from mcp.server.auth.provider import (
    AccessToken,
    AuthorizationCode,
    AuthorizationParams,
    OAuthAuthorizationServerProvider,
    RefreshToken,
    construct_redirect_uri,
)
from mcp.shared.auth import OAuthClientInformationFull, OAuthToken

from ohship.auth import create_access_token, try_decode_access_token
from ohship.config import settings

MCP_SCOPE = "ohship"


@dataclass
class PendingAuth:
    redirect_uri: str
    code_challenge: str
    redirect_uri_provided_explicitly: bool
    client_id: str
    resource: str | None
    scopes: list[str]
    oauth_state: str | None  # original state from MCP client


class OhShipOAuthProvider(OAuthAuthorizationServerProvider[AuthorizationCode, RefreshToken, AccessToken]):
    """Issues OhShip JWTs after users sign in with email/password or Google."""

    def __init__(self) -> None:
        self.clients: dict[str, OAuthClientInformationFull] = {}
        self.auth_codes: dict[str, AuthorizationCode] = {}
        self.tokens: dict[str, AccessToken] = {}
        self.refresh_tokens: dict[str, RefreshToken] = {}
        self.pending: dict[str, PendingAuth] = {}
        # mcp_token -> user_id
        self.token_users: dict[str, str] = {}

    async def get_client(self, client_id: str) -> OAuthClientInformationFull | None:
        return self.clients.get(client_id)

    async def register_client(self, client_info: OAuthClientInformationFull) -> None:
        if not client_info.client_id:
            raise ValueError("No client_id provided")
        self.clients[client_info.client_id] = client_info

    async def authorize(self, client: OAuthClientInformationFull, params: AuthorizationParams) -> str:
        # Internal state for our consent page; preserve client state separately
        consent_state = secrets.token_urlsafe(24)
        self.pending[consent_state] = PendingAuth(
            redirect_uri=str(params.redirect_uri),
            code_challenge=params.code_challenge,
            redirect_uri_provided_explicitly=params.redirect_uri_provided_explicitly,
            client_id=client.client_id or "",
            resource=params.resource,
            scopes=params.scopes or [MCP_SCOPE],
            oauth_state=params.state,
        )
        frontend = settings.frontend_url.rstrip("/")
        return f"{frontend}/oauth/consent?state={consent_state}"

    def get_pending(self, state: str) -> PendingAuth | None:
        return self.pending.get(state)

    def complete_login(self, state: str, user_id: UUID) -> str:
        """Create authorization code after user authenticates; return redirect URL for MCP client."""
        pending = self.pending.pop(state, None)
        if not pending:
            raise ValueError("Invalid or expired OAuth state")

        code = f"os_auth_{secrets.token_urlsafe(24)}"
        auth_code = AuthorizationCode(
            code=code,
            client_id=pending.client_id,
            redirect_uri=AnyUrl(pending.redirect_uri),
            redirect_uri_provided_explicitly=pending.redirect_uri_provided_explicitly,
            expires_at=time.time() + 300,
            scopes=pending.scopes or [MCP_SCOPE],
            code_challenge=pending.code_challenge,
            resource=pending.resource,
            subject=str(user_id),
        )
        self.auth_codes[code] = auth_code

        kwargs: dict[str, str] = {"code": code}
        if pending.oauth_state:
            kwargs["state"] = pending.oauth_state
        return construct_redirect_uri(pending.redirect_uri, **kwargs)

    async def load_authorization_code(
        self, client: OAuthClientInformationFull, authorization_code: str
    ) -> AuthorizationCode | None:
        code = self.auth_codes.get(authorization_code)
        if not code:
            return None
        if code.expires_at < time.time():
            del self.auth_codes[authorization_code]
            return None
        return code

    async def exchange_authorization_code(
        self, client: OAuthClientInformationFull, authorization_code: AuthorizationCode
    ) -> OAuthToken:
        if authorization_code.code not in self.auth_codes:
            raise ValueError("Invalid authorization code")
        if not client.client_id:
            raise ValueError("No client_id provided")

        user_id = UUID(authorization_code.subject) if authorization_code.subject else None
        if not user_id:
            raise ValueError("Authorization code missing subject")

        # Issue the same JWT used by the web UI / REST API
        jwt_token = create_access_token(user_id)
        expires_in = settings.jwt_expire_hours * 3600
        expires_at = int(time.time()) + expires_in

        access = AccessToken(
            token=jwt_token,
            client_id=client.client_id,
            scopes=authorization_code.scopes,
            expires_at=expires_at,
            resource=authorization_code.resource,
            subject=str(user_id),
            claims={"user_id": str(user_id)},
        )
        self.tokens[jwt_token] = access
        self.token_users[jwt_token] = str(user_id)

        refresh = f"os_rt_{secrets.token_urlsafe(32)}"
        self.refresh_tokens[refresh] = RefreshToken(
            token=refresh,
            client_id=client.client_id,
            scopes=authorization_code.scopes,
            expires_at=expires_at + 86400 * 30,
            subject=str(user_id),
        )

        del self.auth_codes[authorization_code.code]

        return OAuthToken(
            access_token=jwt_token,
            token_type="Bearer",
            expires_in=expires_in,
            scope=" ".join(authorization_code.scopes),
            refresh_token=refresh,
        )

    async def load_access_token(self, token: str) -> AccessToken | None:
        cached = self.tokens.get(token)
        if cached:
            if cached.expires_at and cached.expires_at < time.time():
                del self.tokens[token]
                return None
            return cached

        # Also accept JWTs issued by OhShip (web login / this AS)
        user_id = try_decode_access_token(token)
        if not user_id:
            return None
        return AccessToken(
            token=token,
            client_id="ohship",
            scopes=[MCP_SCOPE],
            subject=str(user_id),
            claims={"user_id": str(user_id)},
        )

    async def load_refresh_token(
        self, client: OAuthClientInformationFull, refresh_token: str
    ) -> RefreshToken | None:
        rt = self.refresh_tokens.get(refresh_token)
        if not rt:
            return None
        if rt.expires_at and rt.expires_at < time.time():
            del self.refresh_tokens[refresh_token]
            return None
        return rt

    async def exchange_refresh_token(
        self,
        client: OAuthClientInformationFull,
        refresh_token: RefreshToken,
        scopes: list[str],
    ) -> OAuthToken:
        if refresh_token.token not in self.refresh_tokens:
            raise ValueError("Invalid refresh token")
        if not refresh_token.subject:
            raise ValueError("Refresh token missing subject")

        user_id = UUID(refresh_token.subject)
        jwt_token = create_access_token(user_id)
        expires_in = settings.jwt_expire_hours * 3600
        expires_at = int(time.time()) + expires_in
        use_scopes = scopes or refresh_token.scopes or [MCP_SCOPE]

        access = AccessToken(
            token=jwt_token,
            client_id=client.client_id or "ohship",
            scopes=use_scopes,
            expires_at=expires_at,
            subject=str(user_id),
            claims={"user_id": str(user_id)},
        )
        self.tokens[jwt_token] = access

        new_refresh = f"os_rt_{secrets.token_urlsafe(32)}"
        self.refresh_tokens[new_refresh] = RefreshToken(
            token=new_refresh,
            client_id=client.client_id or "ohship",
            scopes=use_scopes,
            expires_at=int(time.time()) + 86400 * 30,
            subject=str(user_id),
        )
        del self.refresh_tokens[refresh_token.token]

        return OAuthToken(
            access_token=jwt_token,
            token_type="Bearer",
            expires_in=expires_in,
            scope=" ".join(use_scopes),
            refresh_token=new_refresh,
        )

    async def revoke_token(self, token: str, token_type_hint: str | None = None) -> None:  # type: ignore[override]
        self.tokens.pop(token, None)
        self.refresh_tokens.pop(token, None)
        self.token_users.pop(token, None)


# Singleton used by API + MCP
oauth_provider = OhShipOAuthProvider()
