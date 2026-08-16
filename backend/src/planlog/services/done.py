from typing import Any
from uuid import UUID

from sqlmodel import Session, select

from planlog.models import DoneHandoff, DoneRecord, Plan, PlanStatus, User, utcnow
from planlog.services.helpers import build_reconciliation
from planlog.services.orgs import require_membership
from planlog.services.plans import (
    SHIPPABLE_STATUSES,
    PlanTransitionError,
    list_plan_notify_user_ids,
    transition_plan,
)


def post_done(
    session: Session,
    plan: Plan,
    actor: User,
    summary: str,
    links: list[dict[str, Any]],
    residual_notes: str | None = None,
    handoff_notes: str | None = None,
    handoff_to: list[UUID] | None = None,
    # Appended, never inserted: the route and the transition tests call this positionally.
    reconciliation: list[dict[str, Any]] | None = None,
) -> DoneRecord:
    if plan.status == PlanStatus.done:
        raise PlanTransitionError("Plan is already done")
    if plan.status not in SHIPPABLE_STATUSES:
        raise PlanTransitionError(
            f"Cannot post done from status '{plan.status.value}'"
        )

    existing = session.exec(
        select(DoneRecord).where(DoneRecord.plan_id == plan.id)
    ).first()
    if existing is not None:
        raise PlanTransitionError("Done record already exists for this plan")

    # Ship directly: self-approve and claim when intermediate steps were skipped.
    if not plan.approved_by_id:
        plan.approved_at = utcnow()
        plan.approved_by_id = actor.id
    if not plan.claimed_by_id:
        plan.claimed_by_id = actor.id

    done = DoneRecord(
        plan_id=plan.id,
        summary=summary,
        links=links,
        residual_notes=residual_notes,
        handoff_notes=handoff_notes,
        # Always the full criteria list — anything unreported is named, not omitted.
        reconciliation=build_reconciliation(plan.acceptance_criteria, reconciliation),
        posted_by_id=actor.id,
        posted_at=utcnow(),
    )
    session.add(done)
    session.flush()

    all_notify: set[UUID] = set(list_plan_notify_user_ids(session, plan.id))
    if handoff_to:
        all_notify.update(handoff_to)
    for user_id in all_notify:
        require_membership(session, plan.organization_id, user_id)
        session.add(
            DoneHandoff(
                done_record_id=done.id,
                user_id=user_id,
                created_at=utcnow(),
            )
        )

    transition_plan(session, plan, "post_done", actor)
    session.refresh(done)
    return done
