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
    done_record: Optional["DoneRecord"] = Relationship(back_populates="plan")


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
    posted_by_id: UUID = Field(foreign_key="users.id")
    posted_at: datetime = Field(
        default_factory=utcnow,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )

    plan: Optional[Plan] = Relationship(back_populates="done_record")
    posted_by: Optional[User] = Relationship()
