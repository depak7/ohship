"""OAuth consent completion for MCP clients."""

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from planlog.auth import CurrentUser
from planlog.oauth.provider import oauth_provider

router = APIRouter(prefix="/oauth", tags=["oauth"])


class ConsentPreview(BaseModel):
    client_id: str
    scopes: list[str]
    valid: bool


class ConsentApprove(BaseModel):
    state: str


class ConsentResult(BaseModel):
    redirect_uri: str


@router.get("/consent/{state}", response_model=ConsentPreview)
def preview_consent(state: str) -> ConsentPreview:
    pending = oauth_provider.get_pending(state)
    if not pending:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invalid or expired OAuth request")
    return ConsentPreview(client_id=pending.client_id, scopes=pending.scopes, valid=True)


@router.post("/approve", response_model=ConsentResult)
def approve_consent(body: ConsentApprove, user: CurrentUser) -> ConsentResult:
    try:
        redirect_uri = oauth_provider.complete_login(body.state, user.id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    return ConsentResult(redirect_uri=redirect_uri)
