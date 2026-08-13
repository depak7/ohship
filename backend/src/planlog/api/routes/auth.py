from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Header, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from sqlmodel import select

from planlog.auth import (
    CurrentUser,
    DbSession,
    create_access_token,
    generate_api_key,
    hash_api_key,
    verify_password,
)
from planlog.config import settings
from planlog.models import User
from planlog.schemas import (
    AuthResponse,
    GoogleConfigResponse,
    LoginRequest,
    SignupRequest,
    UserCreatedResponse,
    UserCreate,
    UserResponse,
)
from planlog.services.helpers import create_user, verify_bootstrap_token

router = APIRouter(prefix="/auth", tags=["auth"])


def _user_response(user: User) -> UserResponse:
    return UserResponse(
        id=user.id,
        name=user.name,
        email=user.email,
        avatar_url=user.avatar_url,
        created_at=user.created_at,
    )


def _auth_response(user: User, api_key: str | None = None) -> AuthResponse:
    return AuthResponse(
        access_token=create_access_token(user.id),
        user=_user_response(user),
        api_key=api_key,
    )


@router.get("/google/config", response_model=GoogleConfigResponse)
def google_config() -> GoogleConfigResponse:
    enabled = bool(settings.google_client_id and settings.google_client_secret)
    return GoogleConfigResponse(
        enabled=enabled,
        client_id=settings.google_client_id if enabled else None,
    )


@router.post("/signup", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def signup(body: SignupRequest, session: DbSession) -> AuthResponse:
    existing = session.exec(select(User).where(User.email == body.email.lower().strip())).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    user, api_key = create_user(session, body.name.strip(), body.email, password=body.password)
    return _auth_response(user, api_key=api_key)


@router.post("/login", response_model=AuthResponse)
def login(body: LoginRequest, session: DbSession) -> AuthResponse:
    user = session.exec(select(User).where(User.email == body.email.lower().strip())).first()
    if not user or not user.password_hash or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    return _auth_response(user)


@router.get("/me", response_model=UserResponse)
def me(user: CurrentUser) -> UserResponse:
    return _user_response(user)


@router.post("/api-key", response_model=UserCreatedResponse)
def rotate_api_key(session: DbSession, user: CurrentUser) -> UserCreatedResponse:
    api_key = generate_api_key()
    user.api_key_hash = hash_api_key(api_key)
    session.add(user)
    session.commit()
    session.refresh(user)
    return UserCreatedResponse(
        id=user.id,
        name=user.name,
        email=user.email,
        avatar_url=user.avatar_url,
        created_at=user.created_at,
        api_key=api_key,
    )


@router.get("/google/start")
def google_start() -> RedirectResponse:
    if not settings.google_client_id or not settings.google_client_secret:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Google login is not configured. Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET.",
        )
    redirect_uri = f"{settings.api_url.rstrip('/')}/api/v1/auth/google/callback"
    params = urlencode(
        {
            "client_id": settings.google_client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": "openid email profile",
            "access_type": "online",
            "prompt": "select_account",
        }
    )
    return RedirectResponse(f"https://accounts.google.com/o/oauth2/v2/auth?{params}")


@router.get("/google/callback")
def google_callback(session: DbSession, code: str = Query(...)) -> RedirectResponse:
    if not settings.google_client_id or not settings.google_client_secret:
        raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Google login not configured")

    redirect_uri = f"{settings.api_url.rstrip('/')}/api/v1/auth/google/callback"
    with httpx.Client(timeout=20.0) as client:
        token_res = client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code": code,
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            },
        )
        if token_res.status_code >= 400:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Google token exchange failed")
        access_token = token_res.json().get("access_token")
        profile_res = client.get(
            "https://www.googleapis.com/oauth2/v3/userinfo",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if profile_res.status_code >= 400:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Failed to fetch Google profile")
        profile = profile_res.json()

    email = (profile.get("email") or "").lower().strip()
    google_id = profile.get("sub")
    name = profile.get("name") or email.split("@")[0]
    avatar = profile.get("picture")
    if not email or not google_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Google account missing email")

    user = session.exec(select(User).where(User.email == email)).first()
    api_key: str | None = None
    if not user:
        user, api_key = create_user(
            session,
            name=name,
            email=email,
            google_id=google_id,
            avatar_url=avatar,
        )
    else:
        user.google_id = google_id
        user.avatar_url = avatar or user.avatar_url
        if not user.name:
            user.name = name
        session.add(user)
        session.commit()
        session.refresh(user)

    token = create_access_token(user.id)
    frontend = settings.frontend_url.rstrip("/")
    qs = urlencode({"token": token, **({"api_key": api_key} if api_key else {})})
    return RedirectResponse(f"{frontend}/auth/callback?{qs}")


@router.post("/users", response_model=UserCreatedResponse, status_code=status.HTTP_201_CREATED)
def create_user_endpoint(
    body: UserCreate,
    session: DbSession,
    x_bootstrap_token: str | None = Header(default=None),
) -> UserCreatedResponse:
    if not verify_bootstrap_token(x_bootstrap_token):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid or missing bootstrap token",
        )
    existing = session.exec(select(User).where(User.email == body.email.lower().strip())).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    user, api_key = create_user(session, body.name, body.email, password=None)
    return UserCreatedResponse(
        id=user.id,
        name=user.name,
        email=user.email,
        avatar_url=user.avatar_url,
        created_at=user.created_at,
        api_key=api_key,
    )


@router.get("/users", response_model=list[UserResponse])
def list_users(session: DbSession, user: CurrentUser) -> list[UserResponse]:
    users = session.exec(select(User).order_by(User.name)).all()  # type: ignore[attr-defined]
    return [_user_response(u) for u in users]
