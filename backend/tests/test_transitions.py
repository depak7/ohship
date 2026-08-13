import pytest
from sqlmodel import Session

from planlog.models import Organization, OrgMembership, OrgRole, Plan, PlanStatus, User, utcnow
from planlog.services.plans import PlanTransitionError, add_reviewers, transition_plan


@pytest.fixture
def owner(session: Session) -> User:
    from planlog.auth import hash_api_key

    user = User(name="Owner", email="owner@test.com", api_key_hash=hash_api_key("test"))
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


@pytest.fixture
def reviewer(session: Session) -> User:
    from planlog.auth import hash_api_key

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


def test_owner_can_approve(session: Session, plan: Plan, owner: User):
    transition_plan(session, plan, "submit_for_review", owner)
    transition_plan(session, plan, "approve_plan", owner)
    assert plan.status == PlanStatus.approved
    assert plan.approved_by_id == owner.id


def test_post_done_from_in_review_self_approves(session: Session, plan: Plan, owner: User):
    from planlog.services.done import post_done

    transition_plan(session, plan, "submit_for_review", owner)
    assert plan.status == PlanStatus.in_review

    post_done(session, plan, owner, "Shipped from review", [])
    session.refresh(plan)

    assert plan.status == PlanStatus.done
    assert plan.approved_by_id == owner.id
    assert plan.claimed_by_id == owner.id


def test_post_done_from_draft(session: Session, plan: Plan, owner: User):
    from planlog.services.done import post_done

    post_done(session, plan, owner, "Shipped from draft", [])
    session.refresh(plan)

    assert plan.status == PlanStatus.done
    assert plan.approved_by_id == owner.id
    assert plan.claimed_by_id == owner.id


def test_add_reviewers(session: Session, plan: Plan, owner: User, reviewer: User, org: Organization):
    session.add(
        OrgMembership(
            organization_id=org.id,
            user_id=reviewer.id,
            role=OrgRole.member,
            joined_at=utcnow(),
        )
    )
    session.commit()
    transition_plan(session, plan, "submit_for_review", owner)
    add_reviewers(session, plan, owner, [reviewer.id, owner.id])
    from planlog.models import PlanReviewRequest
    from sqlmodel import select

    rows = list(session.exec(select(PlanReviewRequest).where(PlanReviewRequest.plan_id == plan.id)).all())
    assert [row.reviewer_id for row in rows] == [reviewer.id]
