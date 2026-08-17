from uuid import UUID

from fastapi import HTTPException, status
from sqlmodel import Session, select

from planlog.models import DoneHandoff, DoneRecord, Organization, Plan, PlanNotifyRequest, PlanReviewRequest, PlanStatus, Suggestion, User, utcnow


class PlanTransitionError(Exception):
    def __init__(self, message: str, status_code: int = status.HTTP_409_CONFLICT):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


TRANSITIONS: dict[str, tuple[frozenset[PlanStatus], PlanStatus]] = {
    "submit_for_review": (frozenset({PlanStatus.draft, PlanStatus.changes_requested}), PlanStatus.in_review),
    "request_changes": (frozenset({PlanStatus.in_review}), PlanStatus.changes_requested),
    "approve_plan": (frozenset({PlanStatus.in_review}), PlanStatus.approved),
    "claim_plan": (frozenset({PlanStatus.approved}), PlanStatus.in_progress),
    "post_done": (
        frozenset(
            {
                PlanStatus.draft,
                PlanStatus.changes_requested,
                PlanStatus.in_review,
                PlanStatus.approved,
                PlanStatus.in_progress,
            }
        ),
        PlanStatus.done,
    ),
}

SHIPPABLE_STATUSES = TRANSITIONS["post_done"][0]


def get_plan_or_404(session: Session, plan_id: UUID, organization_id: UUID | None = None) -> Plan:
    plan = session.get(Plan, plan_id)
    if not plan:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found")
    if organization_id is not None and plan.organization_id != organization_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found")
    return plan


def assert_editable(plan: Plan) -> None:
    if plan.status not in (PlanStatus.draft, PlanStatus.changes_requested):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Plan cannot be edited in status '{plan.status.value}'",
        )


def approval_kind(plan: Plan) -> str | None:
    """How this plan came to be approved — the distinction the UI must not blur.

    "peer" is the only one that means a second person looked at the plan before code
    existed. "self" is the author approving their own work; "on_ship" is nobody approving
    at all, with post_done filling the field in. Research on 25k agentic pull requests
    found ~79% get a single pair of eyes, so collapsing these three into one green tick
    is the difference between a review layer and a changelog.
    """
    if not plan.approved_by_id:
        return None
    if plan.approved_on_ship:
        return "on_ship"
    return "self" if plan.approved_by_id == plan.owner_id else "peer"


def assert_peer_approval_allowed(session: Session, plan: Plan, actor: User) -> None:
    """Block self-approval when the org has asked for a second pair of eyes."""
    if actor.id != plan.owner_id:
        return
    org = session.get(Organization, plan.organization_id)
    if org and org.require_peer_approval:
        raise PlanTransitionError(
            "This organization requires a second reviewer — the plan's author can't approve it."
        )


def transition_plan(session: Session, plan: Plan, action: str, actor: User | None = None) -> Plan:
    if action not in TRANSITIONS:
        raise PlanTransitionError(f"Unknown action: {action}")

    allowed_from, new_status = TRANSITIONS[action]
    if plan.status not in allowed_from:
        raise PlanTransitionError(
            f"Cannot {action.replace('_', ' ')} from status '{plan.status.value}'"
        )

    plan.status = new_status
    plan.updated_at = utcnow()

    if action == "approve_plan" and actor:
        assert_peer_approval_allowed(session, plan, actor)
        plan.approved_at = utcnow()
        plan.approved_by_id = actor.id
        plan.approved_on_ship = False
    elif action == "claim_plan" and actor:
        plan.claimed_by_id = actor.id

    session.add(plan)
    session.commit()
    session.refresh(plan)
    return plan


def add_reviewers(session: Session, plan: Plan, actor: User, reviewer_ids: list[UUID]) -> Plan:
    from planlog.services.orgs import require_membership

    unique_ids = []
    seen: set[UUID] = set()
    for reviewer_id in reviewer_ids:
        if reviewer_id in seen:
            continue
        seen.add(reviewer_id)
        unique_ids.append(reviewer_id)

    existing = {
        row.reviewer_id
        for row in session.exec(
            select(PlanReviewRequest).where(PlanReviewRequest.plan_id == plan.id)
        ).all()
    }

    for reviewer_id in unique_ids:
        if reviewer_id == actor.id:
            continue
        if reviewer_id in existing:
            continue
        require_membership(session, plan.organization_id, reviewer_id)
        session.add(
            PlanReviewRequest(
                plan_id=plan.id,
                reviewer_id=reviewer_id,
                requested_by_id=actor.id,
                created_at=utcnow(),
            )
        )

    plan.updated_at = utcnow()
    session.add(plan)
    session.commit()
    session.refresh(plan)
    return plan


def add_notifyees(session: Session, plan: Plan, actor: User, notify_ids: list[UUID]) -> Plan:
    from planlog.services.orgs import require_membership

    unique_ids = []
    seen: set[UUID] = set()
    for notify_id in notify_ids:
        if notify_id in seen:
            continue
        seen.add(notify_id)
        unique_ids.append(notify_id)

    existing = {
        row.notify_user_id
        for row in session.exec(
            select(PlanNotifyRequest).where(PlanNotifyRequest.plan_id == plan.id)
        ).all()
    }

    newly_added: list[UUID] = []
    for notify_id in unique_ids:
        if notify_id in existing:
            continue
        require_membership(session, plan.organization_id, notify_id)
        session.add(
            PlanNotifyRequest(
                plan_id=plan.id,
                notify_user_id=notify_id,
                requested_by_id=actor.id,
                created_at=utcnow(),
            )
        )
        newly_added.append(notify_id)

    # Plan already shipped — notify immediately via done handoff.
    if newly_added and plan.status == PlanStatus.done:
        done = session.exec(
            select(DoneRecord).where(DoneRecord.plan_id == plan.id)
        ).first()
        if done:
            existing_handoffs = {
                row.user_id
                for row in session.exec(
                    select(DoneHandoff).where(DoneHandoff.done_record_id == done.id)
                ).all()
            }
            for notify_id in newly_added:
                if notify_id in existing_handoffs:
                    continue
                session.add(
                    DoneHandoff(
                        done_record_id=done.id,
                        user_id=notify_id,
                        created_at=utcnow(),
                    )
                )

    plan.updated_at = utcnow()
    session.add(plan)
    session.commit()
    session.refresh(plan)
    return plan


def list_plan_notify_user_ids(session: Session, plan_id: UUID) -> list[UUID]:
    return list(
        session.exec(
            select(PlanNotifyRequest.notify_user_id).where(PlanNotifyRequest.plan_id == plan_id)
        ).all()
    )


def list_plans(
    session: Session,
    *,
    organization_id: UUID | None = None,
    status: PlanStatus | None = None,
    owner_id: UUID | None = None,
    team: str | None = None,
    project: str | None = None,
    claimed_by: UUID | None = None,
    reviewer_id: UUID | None = None,
    handoff_to: UUID | None = None,
) -> list[Plan]:
    query = select(Plan).order_by(Plan.updated_at.desc())  # type: ignore[attr-defined]
    if organization_id is not None:
        query = query.where(Plan.organization_id == organization_id)
    if status is not None:
        query = query.where(Plan.status == status)
    if owner_id is not None:
        query = query.where(Plan.owner_id == owner_id)
    if team is not None:
        query = query.where(Plan.team == team)
    if project is not None:
        query = query.where(Plan.project == project)
    if claimed_by is not None:
        query = query.where(Plan.claimed_by_id == claimed_by)
    if reviewer_id is not None:
        query = query.join(PlanReviewRequest).where(PlanReviewRequest.reviewer_id == reviewer_id)
    if handoff_to is not None:
        query = (
            query.join(DoneRecord, DoneRecord.plan_id == Plan.id)
            .join(DoneHandoff, DoneHandoff.done_record_id == DoneRecord.id)
            .where(DoneHandoff.user_id == handoff_to)
        )
    return list(session.exec(query).all())


def list_plan_projects(session: Session, organization_id: UUID) -> list[str]:
    rows = session.exec(
        select(Plan.project)
        .where(Plan.organization_id == organization_id, Plan.project.isnot(None))  # type: ignore[union-attr]
        .distinct()
        .order_by(Plan.project)  # type: ignore[arg-type]
    ).all()
    return [row for row in rows if row]


def delete_plan(session: Session, plan: Plan) -> None:
    """Delete a plan and all related rows."""
    for suggestion in session.exec(
        select(Suggestion).where(Suggestion.plan_id == plan.id)
    ).all():
        session.delete(suggestion)
    for review in session.exec(
        select(PlanReviewRequest).where(PlanReviewRequest.plan_id == plan.id)
    ).all():
        session.delete(review)
    for notify in session.exec(
        select(PlanNotifyRequest).where(PlanNotifyRequest.plan_id == plan.id)
    ).all():
        session.delete(notify)
    for done in session.exec(
        select(DoneRecord).where(DoneRecord.plan_id == plan.id)
    ).all():
        for handoff in session.exec(
            select(DoneHandoff).where(DoneHandoff.done_record_id == done.id)
        ).all():
            session.delete(handoff)
        session.delete(done)
    session.delete(plan)
    session.commit()
