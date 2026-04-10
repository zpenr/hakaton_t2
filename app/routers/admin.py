from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth_utils import hash_password
from app.database import get_db
from app.deps import require_roles
from app.models import Organization, Team, User, UserRole
from app.schemas import OrganizationRead, TeamRead, UserCreate, UserRead

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/organizations", response_model=list[OrganizationRead])
def list_organizations(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(UserRole.admin)),
):
    return db.query(Organization).order_by(Organization.name).all()


@router.get("/teams", response_model=list[TeamRead])
def list_teams_all(
    organization_id: int | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(UserRole.admin)),
):
    q = db.query(Team)
    if organization_id is not None:
        q = q.filter(Team.organization_id == organization_id)
    return q.order_by(Team.name).all()


class OrgCreate(BaseModel):
    name: str


class TeamCreate(BaseModel):
    organization_id: int
    name: str
    parent_id: int | None = None


@router.post("/organizations", response_model=OrganizationRead)
def create_organization(
    body: OrgCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(UserRole.admin)),
):
    org = Organization(name=body.name)
    db.add(org)
    db.commit()
    db.refresh(org)
    return org


@router.post("/teams", response_model=TeamRead)
def create_team(
    body: TeamCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(UserRole.admin)),
):
    team = Team(organization_id=body.organization_id, name=body.name, parent_id=body.parent_id)
    db.add(team)
    db.commit()
    db.refresh(team)
    return team


@router.post("/users", response_model=UserRead)
def create_user(body: UserCreate, db: Session = Depends(get_db), _: User = Depends(require_roles(UserRole.admin))):
    if db.query(User).filter(User.email == body.email).first():
        raise HTTPException(status_code=409, detail="Email уже занят")
    user = User(
        email=body.email.strip(),
        full_name=body.full_name,
        hashed_password=hash_password(body.password),
        organization_id=body.organization_id,
        team_id=body.team_id,
        role=body.role,
        is_approved=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user
