from uuid import UUID

from fastapi import HTTPException, status
from sqlmodel import Session, select

from ohship.models import Plan, PlanStatus, User, utcnow


class PlanTransitionError(Exception):
    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


TRANSITIONS: dict[str, tuple[frozenset[PlanStatus], PlanStatus]] = {
    "submit_for_review": (frozenset({PlanStatus.draft, PlanStatus.changes_requested}), PlanStatus.in_review),
    "request_changes": (frozenset({PlanStatus.in_review}), PlanStatus.changes_requested),
    "approve_plan": (frozenset({PlanStatus.in_review}), PlanStatus.approved),
    "claim_plan": (frozenset({PlanStatus.approved}), PlanStatus.in_progress),
    "post_done": (frozenset({PlanStatus.in_progress}), PlanStatus.done),
}


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
        plan.approved_at = utcnow()
        plan.approved_by_id = actor.id
    elif action == "claim_plan" and actor:
        plan.claimed_by_id = actor.id

    session.add(plan)
    session.commit()
    session.refresh(plan)
    return plan


def list_plans(
    session: Session,
    *,
    organization_id: UUID | None = None,
    status: PlanStatus | None = None,
    owner_id: UUID | None = None,
    team: str | None = None,
    project: str | None = None,
    claimed_by: UUID | None = None,
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
    return list(session.exec(query).all())
