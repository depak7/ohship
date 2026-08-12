from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

from ohship.models import OrgRole, PlanStatus


class SignupRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserCreate(BaseModel):
    name: str
    email: EmailStr


class UserResponse(BaseModel):
    id: UUID
    name: str
    email: str
    avatar_url: Optional[str] = None
    created_at: datetime


class UserCreatedResponse(UserResponse):
    api_key: str


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse
    api_key: Optional[str] = None


class UserBrief(BaseModel):
    id: UUID
    name: str
    email: str
    avatar_url: Optional[str] = None


class OrganizationCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)


class OrganizationResponse(BaseModel):
    id: UUID
    name: str
    slug: str
    role: OrgRole
    created_at: datetime
    member_count: int = 0


class InviteCreateResponse(BaseModel):
    token: str
    invite_url: str
    organization_id: UUID
    organization_name: str


class InvitePreview(BaseModel):
    organization_id: UUID
    organization_name: str
    organization_slug: str
    valid: bool


class MemberResponse(BaseModel):
    id: UUID
    name: str
    email: str
    avatar_url: Optional[str] = None
    role: OrgRole
    joined_at: datetime


class DoneLink(BaseModel):
    type: str
    url: str
    label: str


class PlanCreate(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    intent: str = Field(min_length=1)
    scope: Optional[str] = None
    acceptance_criteria: str = Field(min_length=1)
    team: Optional[str] = None
    project: Optional[str] = None
    organization_id: UUID


class PlanUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=500)
    intent: Optional[str] = Field(default=None, min_length=1)
    scope: Optional[str] = None
    acceptance_criteria: Optional[str] = Field(default=None, min_length=1)
    team: Optional[str] = None
    project: Optional[str] = None


class SuggestionCreate(BaseModel):
    content: str = Field(min_length=1)


class RequestChangesBody(BaseModel):
    content: Optional[str] = None


class DoneCreate(BaseModel):
    summary: str = Field(min_length=1)
    links: list[DoneLink] = Field(default_factory=list)
    residual_notes: Optional[str] = None


class SuggestionResponse(BaseModel):
    id: UUID
    plan_id: UUID
    author: UserBrief
    content: str
    created_at: datetime


class DoneResponse(BaseModel):
    id: UUID
    plan_id: UUID
    summary: str
    links: list[dict[str, Any]]
    residual_notes: Optional[str]
    posted_by: UserBrief
    posted_at: datetime


class PlanSummary(BaseModel):
    id: UUID
    organization_id: UUID
    title: str
    status: PlanStatus
    owner: UserBrief
    team: Optional[str]
    project: Optional[str]
    claimed_by: Optional[UserBrief]
    created_at: datetime
    updated_at: datetime


class PlanDetail(PlanSummary):
    intent: str
    scope: Optional[str]
    acceptance_criteria: str
    approved_at: Optional[datetime]
    approved_by: Optional[UserBrief]
    suggestions: list[SuggestionResponse] = Field(default_factory=list)
    done: Optional[DoneResponse] = None
    markdown: str = ""


class PlanListResponse(BaseModel):
    plans: list[PlanSummary]
    total: int


class GoogleConfigResponse(BaseModel):
    enabled: bool
    client_id: Optional[str] = None
