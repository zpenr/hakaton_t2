from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.auth_utils import create_access_token, hash_password, verify_password
from app.database import get_db
from app.deps import get_current_user
from app.models import Organization, Team, User, UserRole
from app.schemas import LoginRequest, RegisterRequest, RegisterResponse, Token, UserRead

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=RegisterResponse)
def register(body: RegisterRequest, db: Session = Depends(get_db)):
    email = body.email.strip()
    if db.query(User).filter(func.lower(User.email) == email.lower()).first():
        raise HTTPException(status_code=409, detail="Этот email уже зарегистрирован")
    org = db.query(Organization).filter(Organization.id == body.organization_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Организация не найдена")
    if body.team_id is not None:
        team = (
            db.query(Team)
            .filter(Team.id == body.team_id, Team.organization_id == body.organization_id)
            .first()
        )
        if not team:
            raise HTTPException(status_code=400, detail="Подразделение не относится к выбранной организации")
    user = User(
        email=email,
        full_name=body.full_name.strip(),
        hashed_password=hash_password(body.password),
        organization_id=body.organization_id,
        team_id=body.team_id,
        role=UserRole.employee,
        is_approved=False,
    )
    db.add(user)
    db.commit()
    return RegisterResponse(
        message="Заявка создана. Дождитесь подтверждения руководителя, затем войдите с тем же email и паролем.",
    )


@router.post("/login", response_model=Token)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    email = body.email.strip()
    user = db.query(User).filter(func.lower(User.email) == email.lower()).first()
    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Wrong email or password")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User disabled")
    if not user.is_approved:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Учётная запись ожидает подтверждения руководителя",
        )
    return Token(access_token=create_access_token(user.email))


@router.get("/me", response_model=UserRead)
def me(user: User = Depends(get_current_user)):
    return user
