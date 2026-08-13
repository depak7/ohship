from typing import Any
from uuid import UUID

from sqlmodel import Session, select

from ohship.models import DoneHandoff, DoneRecord, Plan, PlanStatus, User, utcnow
from ohship.services.orgs import require_membership
from ohship.services.plans import PlanTransitionError, transition_plan


def post_done(
    session: Session,
    plan: Plan,
    actor: User,
    summary: str,
    links: list[dict[str, Any]],
    residual_notes: str | None = None,
    handoff_to: list[UUID] | None = None,
) -> DoneRecord:
    if plan.status != PlanStatus.in_progress:
        raise PlanTransitionError(
            f"Cannot post done from status '{plan.status.value}'"
        )

    existing = session.exec(
        select(DoneRecord).where(DoneRecord.plan_id == plan.id)
    ).first()
    if existing is not None:
        raise PlanTransitionError("Done record already exists for this plan")

    done = DoneRecord(
        plan_id=plan.id,
        summary=summary,
        links=links,
        residual_notes=residual_notes,
        posted_by_id=actor.id,
        posted_at=utcnow(),
    )
    session.add(done)
    session.flush()

    if handoff_to:
        seen: set[UUID] = set()
        for user_id in handoff_to:
            if user_id in seen:
                continue
            seen.add(user_id)
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
