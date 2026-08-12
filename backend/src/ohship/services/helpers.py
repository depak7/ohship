from uuid import UUID

from sqlmodel import Session, select

from ohship.auth import generate_api_key, hash_api_key, hash_password
from ohship.config import settings
from ohship.models import DoneRecord, Plan, Suggestion, User
from ohship.schemas import (
    DoneResponse,
    PlanDetail,
    PlanSummary,
    SuggestionResponse,
    UserBrief,
)


def user_brief(user: User | None) -> UserBrief | None:
    if user is None:
        return None
    return UserBrief(
        id=user.id,
        name=user.name,
        email=user.email,
        avatar_url=user.avatar_url,
    )


def get_user(session: Session, user_id: UUID) -> User | None:
    return session.get(User, user_id)


def plan_to_markdown(plan: Plan) -> str:
    parts = [
        f"# {plan.title}",
        "",
        f"**Status:** `{plan.status.value}`",
        "",
        "## Intent",
        "",
        plan.intent.strip(),
        "",
    ]
    if plan.scope and plan.scope.strip():
        parts.extend(["## Scope", "", plan.scope.strip(), ""])
    parts.extend(["## Acceptance criteria", "", plan.acceptance_criteria.strip(), ""])
    return "\n".join(parts)


def plan_to_summary(session: Session, plan: Plan) -> PlanSummary:
    owner = get_user(session, plan.owner_id)
    claimed = get_user(session, plan.claimed_by_id) if plan.claimed_by_id else None
    return PlanSummary(
        id=plan.id,
        organization_id=plan.organization_id,
        title=plan.title,
        status=plan.status,
        owner=user_brief(owner),  # type: ignore[arg-type]
        team=plan.team,
        project=plan.project,
        claimed_by=user_brief(claimed),
        created_at=plan.created_at,
        updated_at=plan.updated_at,
    )


def plan_to_detail(session: Session, plan: Plan) -> PlanDetail:
    owner = get_user(session, plan.owner_id)
    claimed = get_user(session, plan.claimed_by_id) if plan.claimed_by_id else None
    approved_by = get_user(session, plan.approved_by_id) if plan.approved_by_id else None

    suggestions = session.exec(
        select(Suggestion).where(Suggestion.plan_id == plan.id).order_by(Suggestion.created_at)  # type: ignore[attr-defined]
    ).all()
    suggestion_responses = []
    for s in suggestions:
        author = get_user(session, s.author_id)
        suggestion_responses.append(
            SuggestionResponse(
                id=s.id,
                plan_id=s.plan_id,
                author=user_brief(author),  # type: ignore[arg-type]
                content=s.content,
                created_at=s.created_at,
            )
        )

    done_record = session.exec(
        select(DoneRecord).where(DoneRecord.plan_id == plan.id)
    ).first()
    done_response = None
    if done_record:
        posted_by = get_user(session, done_record.posted_by_id)
        done_response = DoneResponse(
            id=done_record.id,
            plan_id=done_record.plan_id,
            summary=done_record.summary,
            links=done_record.links,
            residual_notes=done_record.residual_notes,
            posted_by=user_brief(posted_by),  # type: ignore[arg-type]
            posted_at=done_record.posted_at,
        )

    return PlanDetail(
        id=plan.id,
        organization_id=plan.organization_id,
        title=plan.title,
        status=plan.status,
        owner=user_brief(owner),  # type: ignore[arg-type]
        team=plan.team,
        project=plan.project,
        claimed_by=user_brief(claimed),
        created_at=plan.created_at,
        updated_at=plan.updated_at,
        intent=plan.intent,
        scope=plan.scope,
        acceptance_criteria=plan.acceptance_criteria,
        approved_at=plan.approved_at,
        approved_by=user_brief(approved_by),
        suggestions=suggestion_responses,
        done=done_response,
        markdown=plan_to_markdown(plan),
    )


def create_user(
    session: Session,
    name: str,
    email: str,
    password: str | None = None,
    google_id: str | None = None,
    avatar_url: str | None = None,
) -> tuple[User, str]:
    api_key = generate_api_key()
    user = User(
        name=name,
        email=email.lower().strip(),
        password_hash=hash_password(password) if password else None,
        google_id=google_id,
        avatar_url=avatar_url,
        api_key_hash=hash_api_key(api_key),
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user, api_key


def ensure_api_key(session: Session, user: User) -> str | None:
    """Return a fresh API key only when creating one; otherwise None."""
    if user.api_key_hash:
        return None
    api_key = generate_api_key()
    user.api_key_hash = hash_api_key(api_key)
    session.add(user)
    session.commit()
    return api_key


def verify_bootstrap_token(token: str | None) -> bool:
    return token is not None and token == settings.bootstrap_token
