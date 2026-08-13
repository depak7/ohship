import secrets
from uuid import UUID

from sqlmodel import Session, select

from planlog.config import settings
from planlog.models import Plan, PlanVisibility, utcnow


def share_url(token: str) -> str:
    return f"{settings.frontend_url.rstrip('/')}/share/{token}"


def ensure_share_token(plan: Plan) -> str:
    if not plan.share_token:
        plan.share_token = secrets.token_urlsafe(24)
    return plan.share_token


def set_plan_share(
    session: Session,
    plan: Plan,
    visibility: PlanVisibility,
    *,
    rotate: bool = False,
) -> Plan:
    plan.visibility = visibility
    if visibility == PlanVisibility.anyone:
        if rotate or not plan.share_token:
            plan.share_token = secrets.token_urlsafe(24)
    else:
        plan.share_token = None
    plan.updated_at = utcnow()
    session.add(plan)
    session.commit()
    session.refresh(plan)
    return plan


def get_plan_by_share_token(session: Session, token: str) -> Plan | None:
    return session.exec(
        select(Plan).where(
            Plan.share_token == token,
            Plan.visibility == PlanVisibility.anyone,
        )
    ).first()
