"""Публичные справочники для регистрации (без авторизации)."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Organization, Team
from app.schemas import OrganizationRead, TeamRead

router = APIRouter(prefix="/api/public", tags=["public"])


@router.get("/organizations", response_model=list[OrganizationRead])
def list_organizations_public(db: Session = Depends(get_db)):
    return db.query(Organization).order_by(Organization.name).all()


@router.get("/teams", response_model=list[TeamRead])
def list_teams_public(
    organization_id: int = Query(..., description="ID организации"),
    db: Session = Depends(get_db),
):
    org = db.query(Organization).filter(Organization.id == organization_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Организация не найдена")
    return (
        db.query(Team)
        .filter(Team.organization_id == organization_id)
        .order_by(Team.name)
        .all()
    )
