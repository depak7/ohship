import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from planlog.auth import hash_api_key
from planlog.models import OrgMembership, OrgRole, Organization, User, utcnow


def auth_headers(api_key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {api_key}"}


def test_share_and_public_plan(
    client: TestClient,
    session: Session,
    user_and_key: tuple[User, str, Organization],
):
    _, api_key, org = user_and_key
    headers = auth_headers(api_key)

    create = client.post(
        "/api/v1/plans",
        json={
            "title": "Public plan",
            "intent": "Share widely",
            "acceptance_criteria": "- Readable",
            "organization_id": str(org.id),
            "project": "share-test",
        },
        headers=headers,
    )
    plan_id = create.json()["id"]

    unauth = client.get(f"/api/v1/plans/{plan_id}")
    assert unauth.status_code == 401

    share = client.post(
        f"/api/v1/plans/{plan_id}/share",
        json={"visibility": "anyone"},
        headers=headers,
    )
    assert share.status_code == 200
    body = share.json()
    assert body["visibility"] == "anyone"
    assert body["share_url"] is not None
    token = body["share_url"].rstrip("/").split("/")[-1]

    public = client.get(f"/api/v1/public/plans/{token}")
    assert public.status_code == 200
    pub = public.json()
    assert pub["title"] == "Public plan"
    assert "email" not in pub["owner_name"].lower()
    assert "agent_prompt" not in pub
    assert pub["markdown"]

    revoke = client.post(
        f"/api/v1/plans/{plan_id}/share",
        json={"visibility": "team"},
        headers=headers,
    )
    assert revoke.status_code == 200
    assert client.get(f"/api/v1/public/plans/{token}").status_code == 404

    unauth_patch = client.patch(
        f"/api/v1/plans/{plan_id}",
        json={"title": "Hacked"},
    )
    assert unauth_patch.status_code == 401


def test_done_handoff_filter(
    client: TestClient,
    session: Session,
    user_and_key: tuple[User, str, Organization],
):
    user, api_key, org = user_and_key
    headers = auth_headers(api_key)
    teammate_key = "dl_handoff_teammate"
    teammate = User(
        name="Handoff Mate",
        email="handoff@test.com",
        api_key_hash=hash_api_key(teammate_key),
    )
    session.add(teammate)
    session.flush()
    session.add(
        OrgMembership(
            organization_id=org.id,
            user_id=teammate.id,
            role=OrgRole.member,
            joined_at=utcnow(),
        )
    )
    session.commit()
    teammate_headers = auth_headers(teammate_key)

    create = client.post(
        "/api/v1/plans",
        json={
            "title": "Handoff plan",
            "intent": "Ship and hand off",
            "acceptance_criteria": "- Done",
            "organization_id": str(org.id),
            "project": "handoff-test",
        },
        headers=headers,
    )
    plan_id = create.json()["id"]

    for endpoint in ("submit", "approve", "claim"):
        client.post(f"/api/v1/plans/{plan_id}/{endpoint}", headers=headers)

    done = client.post(
        f"/api/v1/plans/{plan_id}/done",
        json={
            "summary": "Shipped it",
            "links": [],
            "handoff_to": [str(teammate.id)],
        },
        headers=headers,
    )
    assert done.status_code == 200
    assert done.json()["done"]["handoff_to"][0]["id"] == str(teammate.id)

    mine = client.get(
        f"/api/v1/plans?organization_id={org.id}&handoff_to=me",
        headers=teammate_headers,
    )
    assert mine.status_code == 200
    ids = [p["id"] for p in mine.json()["plans"]]
    assert plan_id in ids

    not_mine = client.get(
        f"/api/v1/plans?organization_id={org.id}&handoff_to=me",
        headers=headers,
    )
    assert plan_id not in [p["id"] for p in not_mine.json()["plans"]]
