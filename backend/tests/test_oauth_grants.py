"""OAuth grants must survive the process that minted them.

The browser POSTs /oauth/approve to one worker and the MCP client POSTs /token to another.
When authorization codes lived in a per-process dict, the second request saw an empty store
and the client got "authorization code does not exist". Each test here mints on one provider
instance and redeems on a second, which is what a two-dyno deploy actually does.
"""

import time
from uuid import uuid4

import pytest
from mcp.server.auth.provider import AuthorizationParams
from mcp.shared.auth import OAuthClientInformationFull
from pydantic import AnyUrl
from planlog.oauth import provider as provider_module
from planlog.oauth.provider import PlanlogOAuthProvider

# opencode's default MCP OAuth callback — a realistic loopback redirect.
REDIRECT = "http://127.0.0.1:19876/mcp/oauth/callback"


@pytest.fixture
def client() -> OAuthClientInformationFull:
    return OAuthClientInformationFull(
        client_id="test-client",
        redirect_uris=[AnyUrl(REDIRECT)],
        grant_types=["authorization_code", "refresh_token"],
    )


async def _authorized_code(prov: PlanlogOAuthProvider, client, user_id) -> str:
    """Run /authorize + /oauth/approve on `prov`, return the minted code."""
    url = await prov.authorize(
        client,
        AuthorizationParams(
            state="client-state",
            scopes=["planlog"],
            code_challenge="challenge123",
            redirect_uri=AnyUrl(REDIRECT),
            redirect_uri_provided_explicitly=True,
            resource=None,
        ),
    )
    state = url.split("state=")[1]
    redirect = prov.complete_login(state, user_id)
    return redirect.split("code=")[1].split("&")[0]


@pytest.mark.anyio
async def test_code_from_another_worker_is_redeemable(test_engine, client):
    """The regression: mint on worker A, redeem on worker B."""
    worker_a = PlanlogOAuthProvider()
    user_id = uuid4()
    code = await _authorized_code(worker_a, client, user_id)

    worker_b = PlanlogOAuthProvider()  # cold process — empty dicts
    assert worker_b.auth_codes == {}

    loaded = await worker_b.load_authorization_code(client, code)
    assert loaded is not None, "authorization code does not exist (the original bug)"
    assert loaded.subject == str(user_id)

    token = await worker_b.exchange_authorization_code(client, loaded)
    assert token.access_token
    assert token.refresh_token


@pytest.mark.anyio
async def test_code_is_single_use_across_workers(test_engine, client):
    worker_a = PlanlogOAuthProvider()
    code = await _authorized_code(worker_a, client, uuid4())

    worker_b = PlanlogOAuthProvider()
    loaded = await worker_b.load_authorization_code(client, code)
    await worker_b.exchange_authorization_code(client, loaded)

    worker_c = PlanlogOAuthProvider()
    assert await worker_c.load_authorization_code(client, code) is None


@pytest.mark.anyio
async def test_expired_code_is_rejected_and_swept(test_engine, client):
    worker_a = PlanlogOAuthProvider()
    code = await _authorized_code(worker_a, client, uuid4())

    stored = worker_a.auth_codes[code]
    stored.expires_at = time.time() - 1
    provider_module._save_grant("code", code, stored.model_dump(mode="json"), stored.expires_at)

    worker_b = PlanlogOAuthProvider()
    assert await worker_b.load_authorization_code(client, code) is None


@pytest.mark.anyio
async def test_refresh_token_survives_restart(test_engine, client):
    worker_a = PlanlogOAuthProvider()
    code = await _authorized_code(worker_a, client, uuid4())
    loaded = await worker_a.load_authorization_code(client, code)
    issued = await worker_a.exchange_authorization_code(client, loaded)

    worker_b = PlanlogOAuthProvider()
    rt = await worker_b.load_refresh_token(client, issued.refresh_token)
    assert rt is not None, "refresh token does not exist after restart"

    rotated = await worker_b.exchange_refresh_token(client, rt, ["planlog"])
    assert rotated.refresh_token != issued.refresh_token

    # The old refresh token must not be reusable, on any worker.
    worker_c = PlanlogOAuthProvider()
    assert await worker_c.load_refresh_token(client, issued.refresh_token) is None


@pytest.mark.anyio
async def test_revoke_removes_the_durable_grant(test_engine, client):
    worker_a = PlanlogOAuthProvider()
    code = await _authorized_code(worker_a, client, uuid4())
    loaded = await worker_a.load_authorization_code(client, code)
    issued = await worker_a.exchange_authorization_code(client, loaded)

    await worker_a.revoke_token(issued.refresh_token)

    worker_b = PlanlogOAuthProvider()
    assert await worker_b.load_refresh_token(client, issued.refresh_token) is None
