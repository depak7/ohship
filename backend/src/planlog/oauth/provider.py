"""MCP OAuth Authorization Server — reuses Planlog email/Google login."""

from __future__ import annotations

import logging
import secrets
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from pydantic import AnyUrl
from sqlmodel import Session, delete

from mcp.server.auth.provider import (
    AccessToken,
    AuthorizationCode,
    AuthorizationParams,
    OAuthAuthorizationServerProvider,
    RefreshToken,
    construct_redirect_uri,
)
from mcp.shared.auth import OAuthClientInformationFull, OAuthToken

from planlog.auth import create_access_token, try_decode_access_token
from planlog.config import settings
from planlog.db import engine
from planlog.models import OAuthClientRecord, OAuthGrantRecord, OAuthPendingRecord

logger = logging.getLogger(__name__)

MCP_SCOPE = "planlog"

# Cursor (and other MCP clients) register a subset of these; authorize uses localhost:8787.
EXTRA_REDIRECT_URIS = [
    "http://localhost:8787/callback",
    "http://127.0.0.1:8787/callback",
    "cursor://anysphere.cursor-mcp/oauth/callback",
    "https://www.cursor.com/agents/mcp/oauth/callback",
]


def _parse_url(value: str) -> AnyUrl | None:
    try:
        return AnyUrl(value)
    except Exception:
        return None


def _with_extra_redirects(client: OAuthClientInformationFull) -> OAuthClientInformationFull:
    existing = [str(u) for u in (client.redirect_uris or [])]
    merged: list[AnyUrl] = []
    seen: set[str] = set()
    for raw in existing + EXTRA_REDIRECT_URIS:
        if raw in seen:
            continue
        parsed = _parse_url(raw)
        if parsed is None:
            continue
        seen.add(raw)
        merged.append(parsed)
    client.redirect_uris = merged
    return client


def _db() -> Session:
    return Session(engine)


def _as_datetime(epoch: float | int | None) -> datetime:
    """Grant expiry as a tz-aware datetime; unset means 'already stale', never 'forever'."""
    return datetime.fromtimestamp(float(epoch or 0), tz=timezone.utc)


def _save_grant(kind: str, key: str, payload: dict[str, Any], expires_at: float | int | None) -> None:
    """Persist an authorization code or refresh token.

    Deliberately not exception-swallowed. If this write fails, the grant only exists in this
    worker's memory and the client's next request will fail with an opaque
    "authorization code does not exist" — better to fail here, where the cause is obvious.
    """
    with _db() as session:
        existing = session.get(OAuthGrantRecord, key)
        if existing:
            existing.payload = payload
            existing.expires_at = _as_datetime(expires_at)
            session.add(existing)
        else:
            session.add(
                OAuthGrantRecord(
                    key=key, kind=kind, payload=payload, expires_at=_as_datetime(expires_at)
                )
            )
        session.commit()


def _load_grant(kind: str, key: str) -> dict[str, Any] | None:
    try:
        with _db() as session:
            row = session.get(OAuthGrantRecord, key)
            if not row or row.kind != kind:
                return None
            return dict(row.payload)
    except Exception:
        logger.exception("Failed to load OAuth %s grant", kind)
        return None


def _delete_grant(key: str) -> None:
    try:
        with _db() as session:
            row = session.get(OAuthGrantRecord, key)
            if row:
                session.delete(row)
                session.commit()
    except Exception:
        logger.exception("Failed to delete OAuth grant")


def _sweep_expired_grants() -> None:
    """Drop expired rows. Called opportunistically — grants are short-lived and high-churn."""
    try:
        with _db() as session:
            session.exec(
                delete(OAuthGrantRecord).where(
                    OAuthGrantRecord.expires_at < datetime.now(timezone.utc)
                )
            )
            session.commit()
    except Exception:
        logger.exception("Failed to sweep expired OAuth grants")


@dataclass
class PendingAuth:
    redirect_uri: str
    code_challenge: str
    redirect_uri_provided_explicitly: bool
    client_id: str
    resource: str | None
    scopes: list[str]
    oauth_state: str | None  # original state from MCP client


class PlanlogOAuthProvider(OAuthAuthorizationServerProvider[AuthorizationCode, RefreshToken, AccessToken]):
    """Issues Planlog JWTs after users sign in with email/password or Google."""

    def __init__(self) -> None:
        self.clients: dict[str, OAuthClientInformationFull] = {}
        self.auth_codes: dict[str, AuthorizationCode] = {}
        self.tokens: dict[str, AccessToken] = {}
        self.refresh_tokens: dict[str, RefreshToken] = {}
        self.pending: dict[str, PendingAuth] = {}
        # mcp_token -> user_id
        self.token_users: dict[str, str] = {}

    async def get_client(self, client_id: str) -> OAuthClientInformationFull | None:
        cached = self.clients.get(client_id)
        if cached:
            return _with_extra_redirects(cached)
        try:
            with _db() as session:
                row = session.get(OAuthClientRecord, client_id)
                if not row:
                    logger.warning("OAuth client not found: %s", client_id)
                    return None
                client = OAuthClientInformationFull.model_validate(row.payload)
                self.clients[client_id] = client
                return _with_extra_redirects(client)
        except Exception:
            logger.exception("Failed to load OAuth client %s", client_id)
            return None

    async def register_client(self, client_info: OAuthClientInformationFull) -> None:
        if not client_info.client_id:
            raise ValueError("No client_id provided")
        client_info = _with_extra_redirects(client_info)
        self.clients[client_info.client_id] = client_info
        try:
            with _db() as session:
                existing = session.get(OAuthClientRecord, client_info.client_id)
                payload = client_info.model_dump(mode="json")
                if existing:
                    existing.payload = payload
                    session.add(existing)
                else:
                    session.add(OAuthClientRecord(client_id=client_info.client_id, payload=payload))
                session.commit()
        except Exception:
            logger.exception("Failed to persist OAuth client %s", client_info.client_id)
        logger.info("Registered OAuth client %s redirects=%s", client_info.client_id, client_info.redirect_uris)

    async def authorize(self, client: OAuthClientInformationFull, params: AuthorizationParams) -> str:
        # Internal state for our consent page; preserve client state separately
        consent_state = secrets.token_urlsafe(24)
        pending = PendingAuth(
            redirect_uri=str(params.redirect_uri),
            code_challenge=params.code_challenge,
            redirect_uri_provided_explicitly=params.redirect_uri_provided_explicitly,
            client_id=client.client_id or "",
            resource=params.resource,
            scopes=params.scopes or [MCP_SCOPE],
            oauth_state=params.state,
        )
        self.pending[consent_state] = pending
        try:
            with _db() as session:
                session.add(OAuthPendingRecord(state=consent_state, payload=asdict(pending)))
                session.commit()
        except Exception:
            logger.exception("Failed to persist OAuth pending state")
        frontend = settings.frontend_url.rstrip("/")
        return f"{frontend}/oauth/consent?state={consent_state}"

    def get_pending(self, state: str) -> PendingAuth | None:
        cached = self.pending.get(state)
        if cached:
            return cached
        try:
            with _db() as session:
                row = session.get(OAuthPendingRecord, state)
                if not row:
                    return None
                pending = PendingAuth(**row.payload)
                self.pending[state] = pending
                return pending
        except Exception:
            logger.exception("Failed to load OAuth pending state %s", state)
            return None

    def _delete_pending(self, state: str) -> None:
        try:
            with _db() as session:
                row = session.get(OAuthPendingRecord, state)
                if row:
                    session.delete(row)
                    session.commit()
        except Exception:
            logger.exception("Failed to delete OAuth pending state %s", state)

    def complete_login(self, state: str, user_id: UUID) -> str:
        """Create authorization code after user authenticates; return redirect URL for MCP client."""
        pending = self.pending.pop(state, None)
        if not pending:
            try:
                with _db() as session:
                    row = session.get(OAuthPendingRecord, state)
                    if row:
                        pending = PendingAuth(**row.payload)
                        session.delete(row)
                        session.commit()
            except Exception:
                logger.exception("Failed to load OAuth pending state %s", state)
        else:
            self._delete_pending(state)
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
        # Must be durable: /token almost always lands on a different worker than this POST.
        _save_grant("code", code, auth_code.model_dump(mode="json"), auth_code.expires_at)
        _sweep_expired_grants()

        kwargs: dict[str, str] = {"code": code}
        if pending.oauth_state:
            kwargs["state"] = pending.oauth_state
        return construct_redirect_uri(pending.redirect_uri, **kwargs)

    async def load_authorization_code(
        self, client: OAuthClientInformationFull, authorization_code: str
    ) -> AuthorizationCode | None:
        code = self.auth_codes.get(authorization_code)
        if not code:
            payload = _load_grant("code", authorization_code)
            if not payload:
                logger.warning("OAuth authorization code not found: %s", authorization_code[:16])
                return None
            code = AuthorizationCode.model_validate(payload)
            self.auth_codes[authorization_code] = code
        if code.expires_at < time.time():
            self.auth_codes.pop(authorization_code, None)
            _delete_grant(authorization_code)
            return None
        return code

    async def exchange_authorization_code(
        self, client: OAuthClientInformationFull, authorization_code: AuthorizationCode
    ) -> OAuthToken:
        # load_authorization_code() has already validated and cached it; re-checking the local
        # dict here would reintroduce the cross-worker failure this method is meant to survive.
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
        refresh_token = RefreshToken(
            token=refresh,
            client_id=client.client_id,
            scopes=authorization_code.scopes,
            expires_at=expires_at + 86400 * 30,
            subject=str(user_id),
        )
        self.refresh_tokens[refresh] = refresh_token
        _save_grant(
            "refresh", refresh, refresh_token.model_dump(mode="json"), refresh_token.expires_at
        )

        # Authorization codes are single-use — drop it from both memory and the durable store.
        self.auth_codes.pop(authorization_code.code, None)
        _delete_grant(authorization_code.code)

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

        # Also accept JWTs issued by Planlog (web login / this AS)
        user_id = try_decode_access_token(token)
        if not user_id:
            return None
        return AccessToken(
            token=token,
            client_id="planlog",
            scopes=[MCP_SCOPE],
            subject=str(user_id),
            claims={"user_id": str(user_id)},
        )

    async def load_refresh_token(
        self, client: OAuthClientInformationFull, refresh_token: str
    ) -> RefreshToken | None:
        rt = self.refresh_tokens.get(refresh_token)
        if not rt:
            payload = _load_grant("refresh", refresh_token)
            if not payload:
                logger.warning("OAuth refresh token not found: %s", refresh_token[:16])
                return None
            rt = RefreshToken.model_validate(payload)
            self.refresh_tokens[refresh_token] = rt
        if rt.expires_at and rt.expires_at < time.time():
            self.refresh_tokens.pop(refresh_token, None)
            _delete_grant(refresh_token)
            return None
        return rt

    async def exchange_refresh_token(
        self,
        client: OAuthClientInformationFull,
        refresh_token: RefreshToken,
        scopes: list[str],
    ) -> OAuthToken:
        # Already validated by load_refresh_token(); see the note in exchange_authorization_code.
        if not refresh_token.subject:
            raise ValueError("Refresh token missing subject")

        user_id = UUID(refresh_token.subject)
        jwt_token = create_access_token(user_id)
        expires_in = settings.jwt_expire_hours * 3600
        expires_at = int(time.time()) + expires_in
        use_scopes = scopes or refresh_token.scopes or [MCP_SCOPE]

        access = AccessToken(
            token=jwt_token,
            client_id=client.client_id or "planlog",
            scopes=use_scopes,
            expires_at=expires_at,
            subject=str(user_id),
            claims={"user_id": str(user_id)},
        )
        self.tokens[jwt_token] = access

        new_refresh = f"os_rt_{secrets.token_urlsafe(32)}"
        rotated = RefreshToken(
            token=new_refresh,
            client_id=client.client_id or "planlog",
            scopes=use_scopes,
            expires_at=int(time.time()) + 86400 * 30,
            subject=str(user_id),
        )
        self.refresh_tokens[new_refresh] = rotated
        _save_grant("refresh", new_refresh, rotated.model_dump(mode="json"), rotated.expires_at)

        self.refresh_tokens.pop(refresh_token.token, None)
        _delete_grant(refresh_token.token)

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
        # Without this the grant survives in the DB and any other worker keeps honouring it.
        _delete_grant(token)


# Singleton used by API + MCP
oauth_provider = PlanlogOAuthProvider()
