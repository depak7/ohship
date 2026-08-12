from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from ohship.auth import CurrentUser, DbSession
from ohship.models import Plan, PlanStatus, utcnow
from ohship.schemas import (
    DoneCreate,
    PlanCreate,
    PlanDetail,
    PlanListResponse,
    PlanUpdate,
    RequestChangesBody,
    SuggestionCreate,
)
from ohship.services.done import post_done
from ohship.services.helpers import plan_to_detail, plan_to_summary
from ohship.services.orgs import require_membership
from ohship.services.plans import (
    PlanTransitionError,
    assert_editable,
    get_plan_or_404,
    list_plans,
    transition_plan,
)
from ohship.services.suggestions import add_suggestion

router = APIRouter(prefix="/plans", tags=["plans"])


def _assert_plan_access(session, plan: Plan, user_id: UUID) -> None:
    require_membership(session, plan.organization_id, user_id)


@router.post("", response_model=PlanDetail, status_code=status.HTTP_201_CREATED)
def create_plan(body: PlanCreate, session: DbSession, user: CurrentUser) -> PlanDetail:
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
) -> PlanListResponse:
    require_membership(session, organization_id, user.id)
    plans = list_plans(
        session,
        organization_id=organization_id,
        status=status_filter,
        owner_id=owner_id,
        team=team,
        project=project,
        claimed_by=claimed_by,
    )
    return PlanListResponse(
        plans=[plan_to_summary(session, p) for p in plans],
        total=len(plans),
    )


@router.get("/{plan_id}", response_model=PlanDetail)
def get_plan(plan_id: UUID, session: DbSession, user: CurrentUser) -> PlanDetail:
    plan = get_plan_or_404(session, plan_id)
    _assert_plan_access(session, plan, user.id)
    return plan_to_detail(session, plan)


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
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=e.message) from e
    return plan_to_detail(session, plan)


@router.post("/{plan_id}/submit", response_model=PlanDetail)
def submit_plan(plan_id: UUID, session: DbSession, user: CurrentUser) -> PlanDetail:
    plan = get_plan_or_404(session, plan_id)
    _assert_plan_access(session, plan, user.id)
    return _handle_transition(session, plan, "submit_for_review", user)


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
def approve_plan(plan_id: UUID, session: DbSession, user: CurrentUser) -> PlanDetail:
    plan = get_plan_or_404(session, plan_id)
    _assert_plan_access(session, plan, user.id)
    return _handle_transition(session, plan, "approve_plan", user)


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


@router.post("/{plan_id}/done", response_model=PlanDetail)
def post_plan_done(
    plan_id: UUID,
    body: DoneCreate,
    session: DbSession,
    user: CurrentUser,
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
        )
    except PlanTransitionError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=e.message) from e
    session.refresh(plan)
    return plan_to_detail(session, plan)
