import pytest
from sqlmodel import Session

from ohship.models import Organization, OrgMembership, OrgRole, Plan, PlanStatus, User, utcnow
from ohship.services.plans import PlanTransitionError, transition_plan


@pytest.fixture
def owner(session: Session) -> User:
    from ohship.auth import hash_api_key

    user = User(name="Owner", email="owner@test.com", api_key_hash=hash_api_key("test"))
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


@pytest.fixture
def reviewer(session: Session) -> User:
    from ohship.auth import hash_api_key

    user = User(name="Reviewer", email="reviewer@test.com", api_key_hash=hash_api_key("test2"))
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


@pytest.fixture
def org(session: Session, owner: User) -> Organization:
    organization = Organization(
        name="Test Org",
        slug="test-org",
        created_by_id=owner.id,
        created_at=utcnow(),
    )
    session.add(organization)
    session.flush()
    session.add(
        OrgMembership(
            organization_id=organization.id,
            user_id=owner.id,
            role=OrgRole.owner,
            joined_at=utcnow(),
        )
    )
    session.commit()
    session.refresh(organization)
    return organization


@pytest.fixture
def plan(session: Session, owner: User, org: Organization) -> Plan:
    p = Plan(
        organization_id=org.id,
        title="Test",
        intent="Do thing",
        acceptance_criteria="- done",
        owner_id=owner.id,
        status=PlanStatus.draft,
        created_at=utcnow(),
        updated_at=utcnow(),
    )
    session.add(p)
    session.commit()
    session.refresh(p)
    return p


def test_submit_for_review(session: Session, plan: Plan, reviewer: User):
    transition_plan(session, plan, "submit_for_review", reviewer)
    assert plan.status == PlanStatus.in_review


def test_full_happy_path(session: Session, plan: Plan, reviewer: User):
    transition_plan(session, plan, "submit_for_review", reviewer)
    transition_plan(session, plan, "approve_plan", reviewer)
    assert plan.approved_by_id == reviewer.id
    transition_plan(session, plan, "claim_plan", reviewer)
    assert plan.claimed_by_id == reviewer.id


def test_invalid_transition(session: Session, plan: Plan, reviewer: User):
    with pytest.raises(PlanTransitionError):
        transition_plan(session, plan, "approve_plan", reviewer)


def test_request_changes(session: Session, plan: Plan, reviewer: User):
    transition_plan(session, plan, "submit_for_review", reviewer)
    transition_plan(session, plan, "request_changes", reviewer)
    assert plan.status == PlanStatus.changes_requested
    transition_plan(session, plan, "submit_for_review", reviewer)
    assert plan.status == PlanStatus.in_review
