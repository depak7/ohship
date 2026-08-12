from datetime import timedelta
from uuid import UUID

from fastapi import HTTPException, status
from sqlmodel import Session, func, select

from ohship.config import settings
from ohship.models import (
    DoneRecord,
    Invite,
    Organization,
    OrgMembership,
    OrgRole,
    Plan,
    Suggestion,
    User,
    as_utc,
    slugify,
    utcnow,
)


def ensure_unique_slug(session: Session, name: str) -> str:
    base = slugify(name)
    slug = base
    n = 1
    while session.exec(select(Organization).where(Organization.slug == slug)).first():
        n += 1
        slug = f"{base}-{n}"
    return slug


def require_membership(session: Session, org_id: UUID, user_id: UUID) -> OrgMembership:
    membership = session.exec(
        select(OrgMembership).where(
            OrgMembership.organization_id == org_id,
            OrgMembership.user_id == user_id,
        )
    ).first()
    if not membership:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a member of this organization")
    return membership


def create_organization(session: Session, name: str, creator: User) -> Organization:
    org = Organization(
        name=name.strip(),
        slug=ensure_unique_slug(session, name),
        created_by_id=creator.id,
        created_at=utcnow(),
    )
    session.add(org)
    session.flush()
    membership = OrgMembership(
        organization_id=org.id,
        user_id=creator.id,
        role=OrgRole.owner,
        joined_at=utcnow(),
    )
    session.add(membership)
    session.commit()
    session.refresh(org)
    return org


def list_user_orgs(session: Session, user_id: UUID) -> list[tuple[Organization, OrgMembership, int]]:
    memberships = session.exec(
        select(OrgMembership).where(OrgMembership.user_id == user_id)
    ).all()
    results = []
    for m in memberships:
        org = session.get(Organization, m.organization_id)
        if not org:
            continue
        count = session.exec(
            select(func.count()).select_from(OrgMembership).where(
                OrgMembership.organization_id == org.id
            )
        ).one()
        results.append((org, m, int(count)))
    results.sort(key=lambda x: x[0].name.lower())
    return results


def create_invite(session: Session, org_id: UUID, creator: User) -> Invite:
    require_membership(session, org_id, creator.id)
    invite = Invite(
        organization_id=org_id,
        created_by_id=creator.id,
        expires_at=utcnow() + timedelta(days=14),
        created_at=utcnow(),
    )
    session.add(invite)
    session.commit()
    session.refresh(invite)
    return invite


def get_invite_by_token(session: Session, token: str) -> Invite | None:
    return session.exec(select(Invite).where(Invite.token == token)).first()


def join_with_invite(session: Session, token: str, user: User) -> Organization:
    invite = get_invite_by_token(session, token)
    if not invite:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invite not found")
    if invite.expires_at and as_utc(invite.expires_at) and as_utc(invite.expires_at) < utcnow():
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="Invite expired")

    existing = session.exec(
        select(OrgMembership).where(
            OrgMembership.organization_id == invite.organization_id,
            OrgMembership.user_id == user.id,
        )
    ).first()
    if not existing:
        session.add(
            OrgMembership(
                organization_id=invite.organization_id,
                user_id=user.id,
                role=OrgRole.member,
                joined_at=utcnow(),
            )
        )
        session.commit()

    org = session.get(Organization, invite.organization_id)
    if not org:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    return org


def list_members(session: Session, org_id: UUID, user_id: UUID) -> list[tuple[User, OrgMembership]]:
    require_membership(session, org_id, user_id)
    memberships = session.exec(
        select(OrgMembership).where(OrgMembership.organization_id == org_id)
    ).all()
    results = []
    for m in memberships:
        u = session.get(User, m.user_id)
        if u:
            results.append((u, m))
    results.sort(key=lambda x: x[0].name.lower())
    return results


def invite_url(token: str) -> str:
    return f"{settings.frontend_url.rstrip('/')}/invite/{token}"


def require_owner(session: Session, org_id: UUID, user_id: UUID) -> OrgMembership:
    membership = require_membership(session, org_id, user_id)
    if membership.role != OrgRole.owner:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only organization owners can delete the organization",
        )
    return membership


def delete_organization(session: Session, org_id: UUID, user_id: UUID) -> None:
    """Delete org and all related plans/invites/memberships. Owners only."""
    require_owner(session, org_id, user_id)
    org = session.get(Organization, org_id)
    if not org:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")

    plans = list(session.exec(select(Plan).where(Plan.organization_id == org_id)).all())
    plan_ids = [p.id for p in plans]
    if plan_ids:
        for suggestion in session.exec(
            select(Suggestion).where(Suggestion.plan_id.in_(plan_ids))  # type: ignore[attr-defined]
        ).all():
            session.delete(suggestion)
        for done in session.exec(
            select(DoneRecord).where(DoneRecord.plan_id.in_(plan_ids))  # type: ignore[attr-defined]
        ).all():
            session.delete(done)
        for plan in plans:
            session.delete(plan)

    for invite in session.exec(select(Invite).where(Invite.organization_id == org_id)).all():
        session.delete(invite)

    for membership in session.exec(
        select(OrgMembership).where(OrgMembership.organization_id == org_id)
    ).all():
        session.delete(membership)

    session.delete(org)
    session.commit()

