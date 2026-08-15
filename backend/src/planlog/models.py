import enum
import secrets
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID, uuid4

from sqlalchemy import Column, DateTime, JSON, Text, UniqueConstraint
from sqlmodel import Field, Relationship, SQLModel


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def as_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def slugify(name: str) -> str:
    base = "".join(c.lower() if c.isalnum() else "-" for c in name).strip("-")
    while "--" in base:
        base = base.replace("--", "-")
    return base[:48] or "org"


class PlanStatus(str, enum.Enum):
    draft = "draft"
    in_review = "in_review"
    changes_requested = "changes_requested"
    approved = "approved"
    in_progress = "in_progress"
    done = "done"


class PlanVisibility(str, enum.Enum):
    team = "team"
    anyone = "anyone"


class OrgRole(str, enum.Enum):
    owner = "owner"
    member = "member"


class User(SQLModel, table=True):
    __tablename__ = "users"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    name: str = Field(max_length=255)
    email: str = Field(max_length=255, unique=True, index=True)
    password_hash: Optional[str] = Field(default=None, max_length=255)
    google_id: Optional[str] = Field(default=None, max_length=255, index=True)
    api_key_hash: Optional[str] = Field(default=None, max_length=255)
    avatar_url: Optional[str] = Field(default=None, max_length=500)
    created_at: datetime = Field(
        default_factory=utcnow,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )

    memberships: list["OrgMembership"] = Relationship(back_populates="user")


class Organization(SQLModel, table=True):
    __tablename__ = "organizations"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    name: str = Field(max_length=255)
    slug: str = Field(max_length=64, unique=True, index=True)
    created_by_id: UUID = Field(foreign_key="users.id")
    created_at: datetime = Field(
        default_factory=utcnow,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )

    memberships: list["OrgMembership"] = Relationship(back_populates="organization")
    invites: list["Invite"] = Relationship(back_populates="organization")
    plans: list["Plan"] = Relationship(back_populates="organization")


class OrgMembership(SQLModel, table=True):
    __tablename__ = "org_memberships"
    __table_args__ = (UniqueConstraint("organization_id", "user_id", name="uq_org_user"),)

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    organization_id: UUID = Field(foreign_key="organizations.id", index=True)
    user_id: UUID = Field(foreign_key="users.id", index=True)
    role: OrgRole = Field(default=OrgRole.member)
    joined_at: datetime = Field(
        default_factory=utcnow,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )

    organization: Optional[Organization] = Relationship(back_populates="memberships")
    user: Optional[User] = Relationship(back_populates="memberships")


class Invite(SQLModel, table=True):
    __tablename__ = "invites"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    organization_id: UUID = Field(foreign_key="organizations.id", index=True)
    token: str = Field(
        default_factory=lambda: secrets.token_urlsafe(24),
        max_length=64,
        unique=True,
        index=True,
    )
    created_by_id: UUID = Field(foreign_key="users.id")
    expires_at: Optional[datetime] = Field(
        default=None, sa_column=Column(DateTime(timezone=True))
    )
    used_at: Optional[datetime] = Field(
        default=None, sa_column=Column(DateTime(timezone=True))
    )
    created_at: datetime = Field(
        default_factory=utcnow,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )

    organization: Optional[Organization] = Relationship(back_populates="invites")


class Plan(SQLModel, table=True):
    __tablename__ = "plans"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    organization_id: UUID = Field(foreign_key="organizations.id", index=True)
    title: str = Field(max_length=500)
    intent: str = Field(sa_column=Column(Text, nullable=False))
    scope: Optional[str] = Field(default=None, sa_column=Column(Text))
    acceptance_criteria: str = Field(sa_column=Column(Text, nullable=False))
    owner_id: UUID = Field(foreign_key="users.id", index=True)
    status: PlanStatus = Field(default=PlanStatus.draft, index=True)
    team: Optional[str] = Field(default=None, max_length=255, index=True)
    project: Optional[str] = Field(default=None, max_length=255, index=True)
    approved_at: Optional[datetime] = Field(
        default=None, sa_column=Column(DateTime(timezone=True))
    )
    approved_by_id: Optional[UUID] = Field(default=None, foreign_key="users.id")
    claimed_by_id: Optional[UUID] = Field(default=None, foreign_key="users.id", index=True)
    visibility: PlanVisibility = Field(default=PlanVisibility.team, index=True)
    share_token: Optional[str] = Field(default=None, max_length=64, unique=True, index=True)
    created_at: datetime = Field(
        default_factory=utcnow,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=utcnow,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )

    organization: Optional[Organization] = Relationship(back_populates="plans")
    suggestions: list["Suggestion"] = Relationship(back_populates="plan")
    review_requests: list["PlanReviewRequest"] = Relationship(back_populates="plan")
    notify_requests: list["PlanNotifyRequest"] = Relationship(back_populates="plan")
    done_record: Optional["DoneRecord"] = Relationship(back_populates="plan")


class PlanReviewRequest(SQLModel, table=True):
    __tablename__ = "plan_review_requests"
    __table_args__ = (UniqueConstraint("plan_id", "reviewer_id", name="uq_plan_reviewer"),)

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    plan_id: UUID = Field(foreign_key="plans.id", index=True)
    reviewer_id: UUID = Field(foreign_key="users.id", index=True)
    requested_by_id: UUID = Field(foreign_key="users.id")
    created_at: datetime = Field(
        default_factory=utcnow,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )

    plan: Optional[Plan] = Relationship(back_populates="review_requests")
    reviewer: Optional[User] = Relationship(
        sa_relationship_kwargs={"foreign_keys": "[PlanReviewRequest.reviewer_id]"}
    )


class PlanNotifyRequest(SQLModel, table=True):
    __tablename__ = "plan_notify_requests"
    __table_args__ = (UniqueConstraint("plan_id", "notify_user_id", name="uq_plan_notify_user"),)

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    plan_id: UUID = Field(foreign_key="plans.id", index=True)
    notify_user_id: UUID = Field(foreign_key="users.id", index=True)
    requested_by_id: UUID = Field(foreign_key="users.id")
    created_at: datetime = Field(
        default_factory=utcnow,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )

    plan: Optional[Plan] = Relationship(back_populates="notify_requests")
    notify_user: Optional[User] = Relationship(
        sa_relationship_kwargs={"foreign_keys": "[PlanNotifyRequest.notify_user_id]"}
    )


class Suggestion(SQLModel, table=True):
    __tablename__ = "suggestions"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    plan_id: UUID = Field(foreign_key="plans.id", index=True)
    author_id: UUID = Field(foreign_key="users.id")
    content: str = Field(sa_column=Column(Text, nullable=False))
    created_at: datetime = Field(
        default_factory=utcnow,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )

    plan: Optional[Plan] = Relationship(back_populates="suggestions")
    author: Optional[User] = Relationship()


class DoneRecord(SQLModel, table=True):
    __tablename__ = "done_records"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    plan_id: UUID = Field(foreign_key="plans.id", unique=True, index=True)
    summary: str = Field(sa_column=Column(Text, nullable=False))
    links: list[dict[str, Any]] = Field(
        default_factory=list,
        sa_column=Column(JSON, nullable=False, server_default="[]"),
    )
    residual_notes: Optional[str] = Field(default=None, sa_column=Column(Text))
    handoff_notes: Optional[str] = Field(default=None, sa_column=Column(Text))
    posted_by_id: UUID = Field(foreign_key="users.id")
    posted_at: datetime = Field(
        default_factory=utcnow,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )

    plan: Optional[Plan] = Relationship(back_populates="done_record")
    posted_by: Optional[User] = Relationship()
    handoffs: list["DoneHandoff"] = Relationship(back_populates="done_record")


class DoneHandoff(SQLModel, table=True):
    __tablename__ = "done_handoffs"
    __table_args__ = (UniqueConstraint("done_record_id", "user_id", name="uq_done_handoff_user"),)

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    done_record_id: UUID = Field(foreign_key="done_records.id", index=True)
    user_id: UUID = Field(foreign_key="users.id", index=True)
    created_at: datetime = Field(
        default_factory=utcnow,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )

    done_record: Optional[DoneRecord] = Relationship(back_populates="handoffs")
    user: Optional[User] = Relationship()


class OAuthClientRecord(SQLModel, table=True):
    """Persisted MCP OAuth client (DCR). In-memory store is lost on Heroku restart."""

    __tablename__ = "oauth_clients"

    client_id: str = Field(primary_key=True, max_length=128)
    payload: dict[str, Any] = Field(sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(
        default_factory=utcnow,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


class OAuthPendingRecord(SQLModel, table=True):
    """Consent-page state between /authorize and /oauth/approve."""

    __tablename__ = "oauth_pending"

    state: str = Field(primary_key=True, max_length=128)
    payload: dict[str, Any] = Field(sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(
        default_factory=utcnow,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


class OAuthGrantRecord(SQLModel, table=True):
    """Authorization codes and refresh tokens.

    These have to outlive the process that minted them: the browser POSTs /oauth/approve to
    one dyno and the MCP client POSTs /token to another, so an in-memory grant produces
    "authorization code does not exist". `expires_at` is stored so rows can be swept.
    """

    __tablename__ = "oauth_grants"

    key: str = Field(primary_key=True, max_length=255)
    kind: str = Field(max_length=16, index=True)  # "code" | "refresh"
    payload: dict[str, Any] = Field(sa_column=Column(JSON, nullable=False))
    expires_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False, index=True)
    )
    created_at: datetime = Field(
        default_factory=utcnow,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
