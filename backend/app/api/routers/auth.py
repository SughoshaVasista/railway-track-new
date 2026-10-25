from datetime import datetime, timedelta, timezone
from uuid import uuid4

import jwt
from fastapi import APIRouter, Depends, Request, status
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.errors import AppError
from app.models import EventLog, User
from app.schemas.auth import LoginRequest, LoginResponse, PublicUser, RegisterRequest, RegistrationResponse
from app.schemas.serializers import serialize_user
from app.security.dependencies import get_current_user
from app.security.passwords import hash_password, verify_password

router = APIRouter(prefix="/api/auth", tags=["authentication"])


def _create_access_token(request: Request, user: User) -> str:
    secret = request.app.state.settings.jwt_secret_key
    if not secret:
        raise AppError(503, "auth_unconfigured", "Authentication is not configured")
    now = datetime.now(timezone.utc)
    expires = now + timedelta(minutes=request.app.state.settings.jwt_access_token_minutes)
    return jwt.encode(
        {"sub": user.id, "iat": now, "exp": expires, "jti": uuid4().hex, "type": "access"},
        secret,
        algorithm="HS256",
    )


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)) -> dict:
    identifier = payload.username.strip().lower()
    user = db.scalar(
        select(User).where(or_(func.lower(User.email) == identifier, func.lower(User.username) == identifier))
    )
    if user is None or not verify_password(payload.password, user.password_hash):
        raise AppError(401, "invalid_credentials", "Email/username or password is incorrect")
    if user.approval_status == "pending":
        raise AppError(403, "pending_approval", "This account is awaiting administrator approval")
    if user.approval_status != "approved" or not user.is_active:
        raise AppError(401, "invalid_credentials", "Email/username or password is incorrect")

    return {
        "token": _create_access_token(request, user),
        "role": user.role,
        "name": user.name,
        "worker_id": user.worker_id,
        "city": user.city,
    }


@router.post("/register", response_model=RegistrationResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: Session = Depends(get_db)) -> dict:
    email = str(payload.email).strip().lower()
    if db.scalar(select(User.id).where(func.lower(User.email) == email)):
        raise AppError(409, "email_exists", "An account with this email already exists")

    # Public role requests are never trusted. Operator/admin requests become a pending worker account.
    user = User(
        id=f"USER-{uuid4().hex}",
        name=payload.name,
        email=email,
        username=None,
        password_hash=hash_password(payload.password),
        role="worker",
        approval_status="pending",
        city=payload.city,
        worker_id=None,
        is_active=True,
        source="registration",
    )
    db.add(user)
    db.add(EventLog(
        actor_user_id=None,
        action="account_registration_requested",
        object_type="user",
        object_id=user.id,
        summary="A new account requested access",
        details={"requested_role": payload.role, "assigned_role": "worker"},
        source="auth",
    ))
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise AppError(409, "email_exists", "An account with this email already exists") from exc
    db.refresh(user)
    return {"message": "Account created and is awaiting administrator approval", "user": serialize_user(user)}


@router.get("/me", response_model=PublicUser)
def me(user: User = Depends(get_current_user)) -> dict:
    return serialize_user(user)
