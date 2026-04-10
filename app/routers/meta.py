from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models import Organization, Team, User
from app.schemas import OrganizationRead, TeamRead

router = APIRouter(prefix="/api", tags=["meta"])


@router.get("/organization", response_model=OrganizationRead)
def my_org(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    org = db.query(Organization).filter(Organization.id == user.organization_id).first()
    return org


@router.get("/teams", response_model=list[TeamRead])
def list_teams(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return (
        db.query(Team)
        .filter(Team.organization_id == user.organization_id)
        .order_by(Team.name)
        .all()
    )
