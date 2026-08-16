from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, status

from planlog import analytics
from planlog.auth import CurrentUser, DbSession
from planlog.models import Organization, OrgRole
from planlog.schemas import (
    InviteCreateResponse,
    InvitePreview,
    MemberResponse,
    OrganizationCreate,
    OrganizationResponse,
)
from planlog.services.orgs import (
    create_invite,
    create_organization,
    delete_organization,
    get_invite_by_token,
    invite_url,
    join_with_invite,
    list_members,
    list_user_orgs,
    require_membership,
)

router = APIRouter(prefix="/orgs", tags=["organizations"])


@router.get("", response_model=list[OrganizationResponse])
def list_orgs(session: DbSession, user: CurrentUser) -> list[OrganizationResponse]:
    rows = list_user_orgs(session, user.id)
    return [
        OrganizationResponse(
            id=org.id,
            name=org.name,
            slug=org.slug,
            role=membership.role,
            created_at=org.created_at,
            member_count=count,
        )
        for org, membership, count in rows
    ]


@router.post("", response_model=OrganizationResponse, status_code=status.HTTP_201_CREATED)
def create_org(
    body: OrganizationCreate,
    session: DbSession,
    user: CurrentUser,
    request: Request,
) -> OrganizationResponse:
    org = create_organization(session, body.name, user)
    analytics.track("org-created", request=request)
    return OrganizationResponse(
        id=org.id,
        name=org.name,
        slug=org.slug,
        role=OrgRole.owner,
        created_at=org.created_at,
        member_count=1,
    )


@router.delete("/{org_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_org(org_id: UUID, session: DbSession, user: CurrentUser) -> None:
    delete_organization(session, org_id, user.id)


@router.get("/{org_id}/members", response_model=list[MemberResponse])
def get_members(org_id: UUID, session: DbSession, user: CurrentUser) -> list[MemberResponse]:
    members = list_members(session, org_id, user.id)
    return [
        MemberResponse(
            id=u.id,
            name=u.name,
            email=u.email,
            avatar_url=u.avatar_url,
            role=m.role,
            joined_at=m.joined_at,
        )
        for u, m in members
    ]


@router.post("/{org_id}/invites", response_model=InviteCreateResponse)
def create_org_invite(org_id: UUID, session: DbSession, user: CurrentUser) -> InviteCreateResponse:
    invite = create_invite(session, org_id, user)
    org = session.get(Organization, org_id)
    if not org:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    return InviteCreateResponse(
        token=invite.token,
        invite_url=invite_url(invite.token),
        organization_id=org.id,
        organization_name=org.name,
    )


@router.get("/invites/{token}", response_model=InvitePreview)
def preview_invite(token: str, session: DbSession) -> InvitePreview:
    invite = get_invite_by_token(session, token)
    if not invite:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invite not found")
    org = session.get(Organization, invite.organization_id)
    if not org:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    from planlog.models import as_utc, utcnow

    expires = as_utc(invite.expires_at)
    valid = not (expires and expires < utcnow())
    return InvitePreview(
        organization_id=org.id,
        organization_name=org.name,
        organization_slug=org.slug,
        valid=valid,
    )


@router.post("/invites/{token}/join", response_model=OrganizationResponse)
def join_invite(token: str, session: DbSession, user: CurrentUser) -> OrganizationResponse:
    org = join_with_invite(session, token, user)
    membership = require_membership(session, org.id, user.id)
    count = len(list_members(session, org.id, user.id))
    return OrganizationResponse(
        id=org.id,
        name=org.name,
        slug=org.slug,
        role=membership.role,
        created_at=org.created_at,
        member_count=count,
    )
