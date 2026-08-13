import os

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from ohship.auth import hash_api_key
from ohship.models import Organization, OrgMembership, OrgRole, User, utcnow


def auth_headers(api_key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {api_key}"}


def test_mcp_oauth_consent_flow(client: TestClient):
    signup = client.post(
        "/api/v1/auth/signup",
        json={"name": "Carol", "email": "carol@test.com", "password": "password123"},
    )
    assert signup.status_code == 201
    token = signup.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Simulate pending authorize state
    from ohship.oauth.provider import PendingAuth, oauth_provider

    state = "teststate123"
    oauth_provider.pending[state] = PendingAuth(
        redirect_uri="http://127.0.0.1:9999/callback",
        code_challenge="challenge",
        redirect_uri_provided_explicitly=True,
        client_id="cursor",
        resource="http://localhost:8000/mcp",
        scopes=["ohship"],
        oauth_state="client-state",
    )

    preview = client.get(f"/api/v1/oauth/consent/{state}", headers=headers)
    assert preview.status_code == 200
    assert preview.json()["client_id"] == "cursor"

    approve = client.post("/api/v1/oauth/approve", json={"state": state}, headers=headers)
    assert approve.status_code == 200
    redirect = approve.json()["redirect_uri"]
    assert "code=" in redirect
    assert "state=client-state" in redirect

    meta = client.get("/.well-known/oauth-authorization-server")
    assert meta.status_code == 200
    assert "authorization_endpoint" in meta.json()



def test_signup_and_org_flow(client: TestClient):
    signup = client.post(
        "/api/v1/auth/signup",
        json={"name": "Bob", "email": "bob@test.com", "password": "password123"},
    )
    assert signup.status_code == 201
    token = signup.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    org = client.post("/api/v1/orgs", json={"name": "Bob Corp"}, headers=headers)
    assert org.status_code == 201
    org_id = org.json()["id"]

    invite = client.post(f"/api/v1/orgs/{org_id}/invites", headers=headers)
    assert invite.status_code == 200
    invite_token = invite.json()["token"]

    preview = client.get(f"/api/v1/orgs/invites/{invite_token}")
    assert preview.status_code == 200
    assert preview.json()["organization_name"] == "Bob Corp"


def test_plan_lifecycle(
    client: TestClient,
    session: Session,
    user_and_key: tuple[User, str, Organization],
):
    os.environ["BOOTSTRAP_TOKEN"] = "dev"
    _, api_key, org = user_and_key
    headers = auth_headers(api_key)
    reviewer_key = "dl_reviewer_key"
    reviewer = User(
        name="Reviewer",
        email="reviewer@test.com",
        api_key_hash=hash_api_key(reviewer_key),
    )
    session.add(reviewer)
    session.flush()
    session.add(
        OrgMembership(
            organization_id=org.id,
            user_id=reviewer.id,
            role=OrgRole.member,
            joined_at=utcnow(),
        )
    )
    session.commit()

    create = client.post(
        "/api/v1/plans",
        json={
            "title": "Ship feature X",
            "intent": "Build feature X",
            "acceptance_criteria": "- Feature works",
            "organization_id": str(org.id),
        },
        headers=headers,
    )
    assert create.status_code == 201
    body = create.json()
    plan_id = body["id"]
    assert "markdown" in body
    assert body["organization_id"] == str(org.id)

    submit = client.post(
        f"/api/v1/plans/{plan_id}/submit",
        json={"reviewer_ids": [str(reviewer.id)]},
        headers=headers,
    )
    assert submit.status_code == 200
    submitted = submit.json()
    assert submitted["status"] == "in_review"
    assert submitted["reviewers"][0]["id"] == str(reviewer.id)
    assert "get_plan" in submitted["agent_prompt"]

    approve = client.post(f"/api/v1/plans/{plan_id}/approve", headers=headers)
    assert approve.status_code == 200
    assert approve.json()["status"] == "approved"

    claim = client.post(f"/api/v1/plans/{plan_id}/claim", headers=headers)
    assert claim.status_code == 200
    assert claim.json()["status"] == "in_progress"

    done = client.post(
        f"/api/v1/plans/{plan_id}/done",
        json={
            "summary": "Shipped feature X",
            "links": [{"type": "pr", "url": "https://github.com/pr/1", "label": "PR #1"}],
        },
        headers=headers,
    )
    assert done.status_code == 200
    body = done.json()
    assert body["status"] == "done"
    assert body["done"]["summary"] == "Shipped feature X"
