from uuid import uuid4

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.errors import AppError
from app.models import EventLog, User
from app.schemas.serializers import serialize_user
from app.security.dependencies import require_roles

router = APIRouter(prefix="/api", tags=["users"])
admin_user = require_roles("admin")


@router.get("/users/pending")
def list_pending_users(
    _admin: User = Depends(admin_user), db: Session = Depends(get_db)
) -> dict[str, list[dict]]:
    users = db.scalars(
        select(User).where(User.approval_status == "pending").order_by(User.created_at, User.id)
    ).all()
    return {"items": [serialize_user(user) for user in users]}


@router.post("/users/{user_id}/approve")
def approve_user(
    user_id: str,
    admin: User = Depends(admin_user),
    db: Session = Depends(get_db),
) -> dict:
    user = db.get(User, user_id)
    if user is None:
        raise AppError(404, "user_not_found", "User was not found")
    if user.approval_status != "pending":
        raise AppError(409, "approval_conflict", "Only pending accounts can be approved")

    user.role = "worker"  # Publicly registered accounts can never become administrators.
    user.approval_status = "approved"
    user.is_active = True
    user.worker_id = user.worker_id or f"WKR-{uuid4().hex[:12].upper()}"
    db.add(EventLog(
        actor_user_id=admin.id,
        action="account_approved",
        object_type="user",
        object_id=user.id,
        summary=f"Approved worker account {user.email}",
        details={"approval_status": "approved", "role": "worker", "worker_id": user.worker_id},
        source="auth",
    ))
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise AppError(409, "approval_conflict", "The account could not be approved") from exc
    db.refresh(user)
    return serialize_user(user)


@router.post("/users/{user_id}/reject")
def reject_user(
    user_id: str,
    admin: User = Depends(admin_user),
    db: Session = Depends(get_db),
) -> dict:
    user = db.get(User, user_id)
    if user is None:
        raise AppError(404, "user_not_found", "User was not found")
    if user.approval_status != "pending":
        raise AppError(409, "approval_conflict", "Only pending accounts can be rejected")

    user.approval_status = "rejected"
    user.is_active = False
    db.add(EventLog(
        actor_user_id=admin.id,
        action="account_rejected",
        object_type="user",
        object_id=user.id,
        summary=f"Rejected access request {user.email}",
        details={"approval_status": "rejected"},
        source="auth",
    ))
    db.commit()
    db.refresh(user)
    return serialize_user(user)


@router.get("/workers")
def list_workers(
    _admin: User = Depends(admin_user), db: Session = Depends(get_db)
) -> dict[str, list[dict]]:
    workers = db.scalars(
        select(User)
        .where(User.role == "worker", User.approval_status == "approved", User.is_active.is_(True))
        .order_by(User.name, User.id)
    ).all()
    return {
        "items": [
            {
                "id": user.id,
                "worker_id": user.worker_id,
                "name": user.name,
                "email": user.email,
                "city": user.city,
                "status": "ACTIVE",
            }
            for user in workers
        ]
    }
