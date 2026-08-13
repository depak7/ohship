from fastapi import APIRouter, HTTPException, status

from ohship.auth import DbSession
from ohship.schemas import PublicPlan
from ohship.services.helpers import plan_to_public
from ohship.services.share import get_plan_by_share_token

router = APIRouter(prefix="/public/plans", tags=["public"])


@router.get("/{token}", response_model=PublicPlan)
def get_public_plan(token: str, session: DbSession) -> PublicPlan:
    plan = get_plan_by_share_token(session, token)
    if not plan:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found")
    return plan_to_public(session, plan)
