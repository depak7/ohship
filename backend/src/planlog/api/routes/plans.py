from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request, status

from planlog import analytics
from planlog.auth import CurrentUser, DbSession
from planlog.models import Plan, PlanStatus, utcnow
from planlog.schemas import (
    DoneCreate,
    NotifyRequestBody,
    PlanCreate,
    PlanDetail,
    PlanListResponse,
    PlanUpdate,
    PublicPlan,
    RequestChangesBody,
    ReviewRequestBody,
    SharePlanBody,
    SuggestionCreate,
)
from planlog.services.done import post_done
from planlog.services.helpers import plan_to_detail, plan_to_summary
from planlog.services.orgs import require_membership
from planlog.services.plans import (
    PlanTransitionError,
    add_notifyees,
    add_reviewers,
    assert_editable,
    delete_plan,
    get_plan_or_404,
    list_plan_projects,
    list_plans,
    transition_plan,
)
from planlog.services.share import set_plan_share
from planlog.services.suggestions import add_suggestion

def _source(request: Request) -> str:
    """web vs mcp — MCP tools loop back over these same HTTP routes, so only the
    User-Agent distinguishes an agent-driven action from a human one."""
    ua = (request.headers.get("user-agent") or "").lower()
    return "mcp" if ua.startswith("planlog-mcp") else "web"


router = APIRouter(prefix="/plans", tags=["plans"])


def _assert_plan_access(session, plan: Plan, user_id: UUID) -> None:
    require_membership(session, plan.organization_id, user_id)


@router.post("", response_model=PlanDetail, status_code=status.HTTP_201_CREATED)
def create_plan(
    body: PlanCreate, session: DbSession, user: CurrentUser, request: Request
) -> PlanDetail:
    require_membership(session, body.organization_id, user.id)
    plan = Plan(
        organization_id=body.organization_id,
        title=body.title,
        intent=body.intent,
        scope=body.scope,
        acceptance_criteria=body.acceptance_criteria,
        owner_id=user.id,
        team=body.team,
        project=body.project,
        status=PlanStatus.draft,
        created_at=utcnow(),
        updated_at=utcnow(),
    )
    session.add(plan)
    session.commit()
    session.refresh(plan)
    analytics.track(
        "plan-created", request=request, source=_source(request), has_project=bool(body.project)
    )
    return plan_to_detail(session, plan)


@router.get("", response_model=PlanListResponse)
def get_plans(
    session: DbSession,
    user: CurrentUser,
    organization_id: UUID = Query(...),
    status_filter: PlanStatus | None = Query(default=None, alias="status"),
    owner_id: UUID | None = None,
    team: str | None = None,
    project: str | None = None,
    claimed_by: UUID | None = None,
    reviewer_id: UUID | None = None,
    handoff_to: str | None = None,
) -> PlanListResponse:
    require_membership(session, organization_id, user.id)
    handoff_user_id: UUID | None = None
    if handoff_to == "me":
        handoff_user_id = user.id
    plans = list_plans(
        session,
        organization_id=organization_id,
        status=status_filter,
        owner_id=owner_id,
        team=team,
        project=project,
        claimed_by=claimed_by,
        reviewer_id=reviewer_id,
        handoff_to=handoff_user_id,
    )
    return PlanListResponse(
        plans=[plan_to_summary(session, p) for p in plans],
        total=len(plans),
    )


@router.get("/projects", response_model=list[str])
def get_plan_projects(
    session: DbSession,
    user: CurrentUser,
    organization_id: UUID = Query(...),
) -> list[str]:
    require_membership(session, organization_id, user.id)
    return list_plan_projects(session, organization_id)


@router.get("/{plan_id}", response_model=PlanDetail)
def get_plan(plan_id: UUID, session: DbSession, user: CurrentUser) -> PlanDetail:
    plan = get_plan_or_404(session, plan_id)
    _assert_plan_access(session, plan, user.id)
    return plan_to_detail(session, plan)


@router.delete("/{plan_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_plan(plan_id: UUID, session: DbSession, user: CurrentUser) -> None:
    plan = get_plan_or_404(session, plan_id)
    _assert_plan_access(session, plan, user.id)
    delete_plan(session, plan)


@router.patch("/{plan_id}", response_model=PlanDetail)
def update_plan(
    plan_id: UUID,
    body: PlanUpdate,
    session: DbSession,
    user: CurrentUser,
) -> PlanDetail:
    plan = get_plan_or_404(session, plan_id)
    _assert_plan_access(session, plan, user.id)
    assert_editable(plan)

    updates = body.model_dump(exclude_unset=True)
    for key, value in updates.items():
        setattr(plan, key, value)
    plan.updated_at = utcnow()
    session.add(plan)
    session.commit()
    session.refresh(plan)
    return plan_to_detail(session, plan)


def _handle_transition(session, plan, action, user):
    try:
        transition_plan(session, plan, action, user)
    except PlanTransitionError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message) from e
    return plan_to_detail(session, plan)


@router.post("/{plan_id}/submit", response_model=PlanDetail)
def submit_plan(
    plan_id: UUID,
    session: DbSession,
    user: CurrentUser,
    body: ReviewRequestBody | None = None,
) -> PlanDetail:
    plan = get_plan_or_404(session, plan_id)
    _assert_plan_access(session, plan, user.id)
    if plan.status in (PlanStatus.draft, PlanStatus.changes_requested):
        _handle_transition(session, plan, "submit_for_review", user)
        plan = get_plan_or_404(session, plan_id)
    elif plan.status != PlanStatus.in_review:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot request review from status '{plan.status.value}'",
        )
    if body and body.reviewer_ids:
        add_reviewers(session, plan, user, body.reviewer_ids)
    return plan_to_detail(session, plan)


@router.post("/{plan_id}/reviewers", response_model=PlanDetail)
def request_reviewers(
    plan_id: UUID,
    body: ReviewRequestBody,
    session: DbSession,
    user: CurrentUser,
) -> PlanDetail:
    plan = get_plan_or_404(session, plan_id)
    _assert_plan_access(session, plan, user.id)
    if plan.status not in (PlanStatus.draft, PlanStatus.changes_requested, PlanStatus.in_review):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot request reviewers from status '{plan.status.value}'",
        )
    add_reviewers(session, plan, user, body.reviewer_ids)
    return plan_to_detail(session, plan)


@router.post("/{plan_id}/notifyees", response_model=PlanDetail)
def request_notifyees(
    plan_id: UUID,
    body: NotifyRequestBody,
    session: DbSession,
    user: CurrentUser,
) -> PlanDetail:
    plan = get_plan_or_404(session, plan_id)
    _assert_plan_access(session, plan, user.id)
    add_notifyees(session, plan, user, body.notify_ids)
    return plan_to_detail(session, plan)


@router.post("/{plan_id}/suggestions", response_model=PlanDetail)
def create_suggestion(
    plan_id: UUID,
    body: SuggestionCreate,
    session: DbSession,
    user: CurrentUser,
) -> PlanDetail:
    plan = get_plan_or_404(session, plan_id)
    _assert_plan_access(session, plan, user.id)
    add_suggestion(session, plan.id, user, body.content)
    plan.updated_at = utcnow()
    session.add(plan)
    session.commit()
    session.refresh(plan)
    return plan_to_detail(session, plan)


@router.post("/{plan_id}/approve", response_model=PlanDetail)
def approve_plan(
    plan_id: UUID, session: DbSession, user: CurrentUser, request: Request
) -> PlanDetail:
    plan = get_plan_or_404(session, plan_id)
    _assert_plan_access(session, plan, user.id)
    detail = _handle_transition(session, plan, "approve_plan", user)
    analytics.track("plan-approved", request=request, source=_source(request))
    return detail


@router.post("/{plan_id}/request-changes", response_model=PlanDetail)
def request_changes(
    plan_id: UUID,
    session: DbSession,
    user: CurrentUser,
    body: RequestChangesBody | None = None,
) -> PlanDetail:
    plan = get_plan_or_404(session, plan_id)
    _assert_plan_access(session, plan, user.id)
    if body and body.content:
        add_suggestion(session, plan.id, user, body.content)
    return _handle_transition(session, plan, "request_changes", user)


@router.post("/{plan_id}/claim", response_model=PlanDetail)
def claim_plan(plan_id: UUID, session: DbSession, user: CurrentUser) -> PlanDetail:
    plan = get_plan_or_404(session, plan_id)
    _assert_plan_access(session, plan, user.id)
    return _handle_transition(session, plan, "claim_plan", user)


@router.post("/{plan_id}/share", response_model=PlanDetail)
def share_plan(
    plan_id: UUID,
    body: SharePlanBody,
    session: DbSession,
    user: CurrentUser,
) -> PlanDetail:
    plan = get_plan_or_404(session, plan_id)
    _assert_plan_access(session, plan, user.id)
    set_plan_share(session, plan, body.visibility, rotate=body.rotate)
    return plan_to_detail(session, plan)


@router.post("/{plan_id}/done", response_model=PlanDetail)
def post_plan_done(
    plan_id: UUID,
    body: DoneCreate,
    session: DbSession,
    user: CurrentUser,
    request: Request,
) -> PlanDetail:
    plan = get_plan_or_404(session, plan_id)
    _assert_plan_access(session, plan, user.id)
    try:
        post_done(
            session,
            plan,
            user,
            body.summary,
            [link.model_dump() for link in body.links],
            body.residual_notes,
            body.handoff_notes,
            body.handoff_to,
            [item.model_dump() for item in body.reconciliation],
        )
    except PlanTransitionError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=e.message) from e
    session.refresh(plan)
    links = len(body.links)
    outcomes = (plan.done_record.reconciliation if plan.done_record else []) or []
    analytics.track(
        "done-posted",
        request=request,
        source=_source(request),
        links="3+" if links >= 3 else str(links),
        has_handoff=bool(body.handoff_notes),
        # Does anyone actually reconcile, and does drift show up when they do?
        reconciled=bool(body.reconciliation),
        drifted=any(o.get("status") in ("changed", "dropped") for o in outcomes),
    )
    return plan_to_detail(session, plan)
