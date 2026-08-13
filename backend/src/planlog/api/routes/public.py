from fastapi import APIRouter, HTTPException, status

from planlog.auth import DbSession
from planlog.schemas import PublicPlan
from planlog.services.helpers import plan_to_public
from planlog.services.share import get_plan_by_share_token

router = APIRouter(prefix="/public/plans", tags=["public"])


@router.get("/{token}", response_model=PublicPlan)
def get_public_plan(token: str, session: DbSession) -> PublicPlan:
    plan = get_plan_by_share_token(session, token)
    if not plan:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found")
    return plan_to_public(session, plan)
