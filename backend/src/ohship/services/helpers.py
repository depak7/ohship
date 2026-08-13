from uuid import UUID

from sqlmodel import Session, select

from ohship.auth import generate_api_key, hash_api_key, hash_password
from ohship.config import settings
from ohship.models import DoneHandoff, DoneRecord, Plan, PlanReviewRequest, Suggestion, User
from ohship.schemas import (
    DoneResponse,
    PlanDetail,
    PlanSummary,
    PublicDoneResponse,
    PublicPlan,
    ReviewerResponse,
    SuggestionResponse,
    UserBrief,
)
from ohship.services.share import share_url


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


def plan_web_url(plan: Plan) -> str:
    return f"{settings.frontend_url.rstrip('/')}/plans/{plan.id}"


def agent_review_prompt(plan: Plan) -> str:
    return (
        f"Review this OhShip plan in your coding agent (Cursor with the OhShip MCP server).\n\n"
        f"Title: {plan.title}\n"
        f"Plan ID: {plan.id}\n"
        f"Web: {plan_web_url(plan)}\n\n"
        f"Use OhShip MCP tools:\n"
        f"1. get_plan(plan_id=\"{plan.id}\")\n"
        f"2. Read intent, scope, and acceptance criteria\n"
        f"3. approve_plan(plan_id=\"{plan.id}\") or request_changes(plan_id=\"{plan.id}\", content=\"...\")\n"
    )


def list_reviewers(session: Session, plan: Plan) -> list[ReviewerResponse]:
    rows = session.exec(
        select(PlanReviewRequest)
        .where(PlanReviewRequest.plan_id == plan.id)
        .order_by(PlanReviewRequest.created_at)  # type: ignore[attr-defined]
    ).all()
    reviewers: list[ReviewerResponse] = []
    for row in rows:
        reviewer = get_user(session, row.reviewer_id)
        requested_by = get_user(session, row.requested_by_id)
        if not reviewer:
            continue
        brief = user_brief(reviewer)
        reviewers.append(
            ReviewerResponse(
                id=brief.id,
                name=brief.name,
                email=brief.email,
                avatar_url=brief.avatar_url,
                requested_by=user_brief(requested_by),
                requested_at=row.created_at,
            )
        )
    return reviewers


def list_done_handoffs(session: Session, done_record_id) -> list[UserBrief]:
    rows = session.exec(
        select(DoneHandoff)
        .where(DoneHandoff.done_record_id == done_record_id)
        .order_by(DoneHandoff.created_at)  # type: ignore[attr-defined]
    ).all()
    handoffs: list[UserBrief] = []
    for row in rows:
        user = get_user(session, row.user_id)
        brief = user_brief(user)
        if brief:
            handoffs.append(brief)
    return handoffs


def plan_share_url(plan: Plan) -> str | None:
    if plan.share_token and plan.visibility.value == "anyone":
        return share_url(plan.share_token)
    return None


def plan_to_markdown(plan: Plan, reviewers: list[ReviewerResponse] | None = None) -> str:
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
    if reviewers:
        names = ", ".join(r.name for r in reviewers)
        parts.extend(["## Requested reviewers", "", names, ""])
    return "\n".join(parts)


def plan_to_summary(session: Session, plan: Plan) -> PlanSummary:
    owner = get_user(session, plan.owner_id)
    claimed = get_user(session, plan.claimed_by_id) if plan.claimed_by_id else None
    reviewers = list_reviewers(session, plan)
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
        reviewers=[UserBrief(id=r.id, name=r.name, email=r.email, avatar_url=r.avatar_url) for r in reviewers],
        visibility=plan.visibility,
        share_url=plan_share_url(plan),
    )


def plan_to_detail(session: Session, plan: Plan) -> PlanDetail:
    owner = get_user(session, plan.owner_id)
    claimed = get_user(session, plan.claimed_by_id) if plan.claimed_by_id else None
    approved_by = get_user(session, plan.approved_by_id) if plan.approved_by_id else None
    reviewers = list_reviewers(session, plan)

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
            handoff_to=list_done_handoffs(session, done_record.id),
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
        markdown=plan_to_markdown(plan, reviewers),
        reviewers=[UserBrief(id=r.id, name=r.name, email=r.email, avatar_url=r.avatar_url) for r in reviewers],
        agent_prompt=agent_review_prompt(plan),
        visibility=plan.visibility,
        share_url=plan_share_url(plan),
    )


def plan_to_public(session: Session, plan: Plan) -> PublicPlan:
    owner = get_user(session, plan.owner_id)
    reviewers = list_reviewers(session, plan)

    done_record = session.exec(
        select(DoneRecord).where(DoneRecord.plan_id == plan.id)
    ).first()
    public_done = None
    if done_record:
        posted_by = get_user(session, done_record.posted_by_id)
        public_done = PublicDoneResponse(
            summary=done_record.summary,
            links=done_record.links,
            residual_notes=done_record.residual_notes,
            posted_by_name=posted_by.name if posted_by else "Unknown",
            posted_at=done_record.posted_at,
        )

    return PublicPlan(
        title=plan.title,
        status=plan.status,
        owner_name=owner.name if owner else "Unknown",
        markdown=plan_to_markdown(plan, reviewers),
        done=public_done,
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
