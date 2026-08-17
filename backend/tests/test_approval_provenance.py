"""An approval is only worth recording if you can tell what kind it was.

`post_done` fills in `approved_by` when no review happened, which made a plan nobody looked
at render identically to one a colleague signed off. These pin the three cases apart.
"""

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from planlog.auth import hash_api_key
from planlog.models import Organization, OrgMembership, OrgRole, Plan, User
from planlog.services.done import post_done
from planlog.services.plans import PlanTransitionError, approval_kind, transition_plan


def _user(session: Session, name: str, email: str) -> User:
    user = User(name=name, email=email, api_key_hash=hash_api_key(email))
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


@pytest.fixture
def author(session: Session) -> User:
    return _user(session, "Author", "author@test.com")


@pytest.fixture
def reviewer(session: Session) -> User:
    return _user(session, "Reviewer", "reviewer@test.com")


@pytest.fixture
def org(session: Session, author: User, reviewer: User) -> Organization:
    org = Organization(name="Acme", slug="acme", created_by_id=author.id)
    session.add(org)
    session.commit()
    session.refresh(org)
    for user in (author, reviewer):
        session.add(OrgMembership(organization_id=org.id, user_id=user.id, role=OrgRole.member))
    session.commit()
    return org


@pytest.fixture
def plan(session: Session, org: Organization, author: User) -> Plan:
    plan = Plan(
        organization_id=org.id,
        title="Ship it",
        intent="why",
        acceptance_criteria="- works",
        owner_id=author.id,
        project="checkout",
    )
    session.add(plan)
    session.commit()
    session.refresh(plan)
    return plan


# --------------------------------------------------------------------------- the three kinds


def test_peer_approval(session: Session, plan: Plan, author: User, reviewer: User):
    transition_plan(session, plan, "submit_for_review", author)
    transition_plan(session, plan, "approve_plan", reviewer)
    assert approval_kind(plan) == "peer"


def test_author_approving_own_plan_is_self_not_peer(session: Session, plan: Plan, author: User):
    transition_plan(session, plan, "submit_for_review", author)
    transition_plan(session, plan, "approve_plan", author)
    assert approval_kind(plan) == "self"


def test_shipping_without_review_is_on_ship(session: Session, plan: Plan, author: User):
    """The silent case: post_done writes approved_by itself, and nobody ever reviewed."""
    post_done(session, plan, author, "Shipped", [])
    assert plan.approved_by_id == author.id  # the field is populated…
    assert plan.approved_on_ship is True  # …but it was never a review
    assert approval_kind(plan) == "on_ship"


def test_a_real_approval_is_not_relabelled_on_ship(
    session: Session, plan: Plan, author: User, reviewer: User
):
    transition_plan(session, plan, "submit_for_review", author)
    transition_plan(session, plan, "approve_plan", reviewer)
    post_done(session, plan, author, "Shipped", [])
    assert plan.approved_on_ship is False
    assert approval_kind(plan) == "peer"


def test_unapproved_plan_has_no_kind(plan: Plan):
    assert approval_kind(plan) is None


# --------------------------------------------------------------------------- the org rule


def test_require_peer_approval_blocks_self_approval(
    session: Session, org: Organization, plan: Plan, author: User
):
    org.require_peer_approval = True
    session.add(org)
    session.commit()

    transition_plan(session, plan, "submit_for_review", author)
    with pytest.raises(PlanTransitionError, match="second reviewer"):
        transition_plan(session, plan, "approve_plan", author)


def test_require_peer_approval_still_allows_a_colleague(
    session: Session, org: Organization, plan: Plan, author: User, reviewer: User
):
    org.require_peer_approval = True
    session.add(org)
    session.commit()

    transition_plan(session, plan, "submit_for_review", author)
    transition_plan(session, plan, "approve_plan", reviewer)
    assert approval_kind(plan) == "peer"


def test_require_peer_approval_blocks_shipping_unreviewed(
    session: Session, org: Organization, plan: Plan, author: User
):
    """Otherwise post_done is a hole straight through the rule."""
    org.require_peer_approval = True
    session.add(org)
    session.commit()

    with pytest.raises(PlanTransitionError, match="approved plan before Done"):
        post_done(session, plan, author, "Shipped", [])


# --------------------------------------------------------------------------- API


def test_api_exposes_approval_kind(client: TestClient):
    token = client.post(
        "/api/v1/auth/signup",
        json={"name": "Ana", "email": "ana@test.com", "password": "password123"},
    ).json()["access_token"]
    auth = {"Authorization": f"Bearer {token}"}
    org = client.post("/api/v1/orgs", json={"name": "Acme"}, headers=auth).json()
    plan = client.post(
        "/api/v1/plans",
        json={
            "organization_id": org["id"],
            "title": "Solo ship",
            "intent": "why",
            "acceptance_criteria": "- works",
            "project": "checkout",
        },
        headers=auth,
    ).json()

    body = client.post(
        f"/api/v1/plans/{plan['id']}/done",
        json={"summary": "shipped", "links": []},
        headers=auth,
    ).json()
    # Solo developer, no review: the API must say so rather than reporting a plain approval.
    assert body["approval_kind"] == "on_ship"
    assert body["approved_by"]["name"] == "Ana"
