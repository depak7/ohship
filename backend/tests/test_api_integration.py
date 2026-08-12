import os

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from ohship.api.main import app
from ohship.auth import hash_api_key
from ohship.db import get_session
from ohship.models import Organization, OrgMembership, OrgRole, User, utcnow
from ohship.services.orgs import create_organization


@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture(name="client")
def client_fixture(session: Session):
    def get_session_override():
        yield session

    app.dependency_overrides[get_session] = get_session_override
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


@pytest.fixture(name="user_and_key")
def user_and_key_fixture(session: Session) -> tuple[User, str, Organization]:
    key = "dl_test_integration_key"
    user = User(name="Alice", email="alice@test.com", api_key_hash=hash_api_key(key))
    session.add(user)
    session.commit()
    session.refresh(user)
    org = create_organization(session, "Acme", user)
    return user, key, org


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


def test_plan_lifecycle(client: TestClient, user_and_key: tuple[User, str, Organization]):
    os.environ["BOOTSTRAP_TOKEN"] = "dev"
    _, api_key, org = user_and_key
    headers = auth_headers(api_key)

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

    submit = client.post(f"/api/v1/plans/{plan_id}/submit", headers=headers)
    assert submit.status_code == 200
    assert submit.json()["status"] == "in_review"

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
