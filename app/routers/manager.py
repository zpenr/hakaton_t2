from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.deps import require_roles
from app.models import User, UserRole
from app.schemas import PendingUserRead, UserRead

router = APIRouter(prefix="/api/manager", tags=["manager"])


@router.get("/pending-users", response_model=list[PendingUserRead])
def list_pending_users(
    db: Session = Depends(get_db),
    viewer: User = Depends(require_roles(UserRole.manager, UserRole.admin)),
):
    """Пользователи организации без подтверждения (обычно после регистрации)."""
    rows = (
        db.query(User)
        .options(joinedload(User.team))
        .filter(
            User.organization_id == viewer.organization_id,
            User.is_approved.is_(False),
            User.is_active.is_(True),
        )
        .order_by(User.id.desc())
        .all()
    )
    return [
        PendingUserRead(
            id=u.id,
            email=u.email,
            full_name=u.full_name,
            team_id=u.team_id,
            team_name=u.team.name if u.team else None,
            role=u.role,
        )
        for u in rows
    ]


@router.post("/users/{user_id}/approve", response_model=UserRead)
def approve_user(
    user_id: int,
    db: Session = Depends(get_db),
    viewer: User = Depends(require_roles(UserRole.manager, UserRole.admin)),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user or user.organization_id != viewer.organization_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Пользователь не найден")
    if user.is_approved:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Уже подтверждён")
    user.is_approved = True
    db.commit()
    db.refresh(user)
    return user
