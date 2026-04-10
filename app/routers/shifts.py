from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.deps import get_current_user, require_roles
from app.models import Shift, ShiftStatus, User, UserRole
from app.schemas import ShiftCreate, ShiftRead, ShiftReadWithUser, ShiftUpdate

router = APIRouter(prefix="/api/shifts", tags=["shifts"])

MAX_PLAN_DAYS_AHEAD = 14


def _within_plan_window(work_date: date, today: date) -> bool:
    end = today + timedelta(days=MAX_PLAN_DAYS_AHEAD)
    return today <= work_date <= end


@router.get("/my", response_model=list[ShiftRead])
def list_my_shifts(
    from_date: date | None = None,
    to_date: date | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    q = db.query(Shift).filter(Shift.user_id == user.id)
    if from_date:
        q = q.filter(Shift.work_date >= from_date)
    if to_date:
        q = q.filter(Shift.work_date <= to_date)
    return q.order_by(Shift.work_date).all()


@router.post("/my", response_model=ShiftRead)
def create_my_shift(body: ShiftCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    today = date.today()
    if not _within_plan_window(body.work_date, today):
        raise HTTPException(
            status_code=400,
            detail=f"Дата должна быть в пределах сегодня и +{MAX_PLAN_DAYS_AHEAD} дней",
        )
    if body.plan_end <= body.plan_start:
        raise HTTPException(status_code=400, detail="Конец смены должен быть позже начала")
    existing = (
        db.query(Shift).filter(Shift.user_id == user.id, Shift.work_date == body.work_date).first()
    )
    if existing:
        raise HTTPException(status_code=409, detail="На эту дату смена уже есть — используйте обновление")
    shift = Shift(
        user_id=user.id,
        work_date=body.work_date,
        plan_start=body.plan_start,
        plan_end=body.plan_end,
        status=ShiftStatus.draft,
        comment=body.comment,
    )
    db.add(shift)
    db.commit()
    db.refresh(shift)
    return shift


@router.patch("/my/{shift_id}", response_model=ShiftRead)
def update_my_shift(
    shift_id: int,
    body: ShiftUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    shift = db.query(Shift).filter(Shift.id == shift_id, Shift.user_id == user.id).first()
    if not shift:
        raise HTTPException(status_code=404, detail="Смена не найдена")
    today = date.today()
    if not _within_plan_window(shift.work_date, today):
        raise HTTPException(status_code=400, detail="Редактирование вне окна планирования запрещено")
    if shift.status == ShiftStatus.confirmed and user.role == UserRole.employee:
        raise HTTPException(status_code=400, detail="Подтверждённую смену сотрудник не меняет")

    data = body.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(shift, k, v)
    if body.plan_start is not None or body.plan_end is not None:
        if shift.plan_end <= shift.plan_start:
            raise HTTPException(status_code=400, detail="Конец смены должен быть позже начала")
    db.commit()
    db.refresh(shift)
    return shift


@router.delete("/my/{shift_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_my_shift(shift_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    shift = db.query(Shift).filter(Shift.id == shift_id, Shift.user_id == user.id).first()
    if not shift:
        raise HTTPException(status_code=404, detail="Смена не найдена")
    if shift.status == ShiftStatus.confirmed:
        raise HTTPException(status_code=400, detail="Нельзя удалить подтверждённую смену")
    db.delete(shift)
    db.commit()


@router.post("/my/submit-week", response_model=list[ShiftRead])
def submit_my_shifts(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Отправить все черновики в статус submitted (для согласования руководителем)."""
    drafts = db.query(Shift).filter(Shift.user_id == user.id, Shift.status == ShiftStatus.draft).all()
    for s in drafts:
        s.status = ShiftStatus.submitted
    db.commit()
    for s in drafts:
        db.refresh(s)
    return drafts


# --- Manager / Admin: видимость по организации ---


@router.get("/org", response_model=list[ShiftReadWithUser])
def list_org_shifts(
    from_date: date | None = None,
    to_date: date | None = None,
    team_id: int | None = None,
    db: Session = Depends(get_db),
    viewer: User = Depends(require_roles(UserRole.manager, UserRole.admin)),
):
    q = (
        db.query(Shift)
        .options(joinedload(Shift.user).joinedload(User.team))
        .join(User)
        .filter(User.organization_id == viewer.organization_id)
    )
    if team_id is not None:
        q = q.filter(User.team_id == team_id)
    if from_date:
        q = q.filter(Shift.work_date >= from_date)
    if to_date:
        q = q.filter(Shift.work_date <= to_date)
    rows = q.order_by(Shift.work_date, User.full_name).all()
    out: list[ShiftReadWithUser] = []
    for s in rows:
        u = s.user
        out.append(
            ShiftReadWithUser(
                id=s.id,
                user_id=s.user_id,
                work_date=s.work_date,
                plan_start=s.plan_start,
                plan_end=s.plan_end,
                fact_start=s.fact_start,
                fact_end=s.fact_end,
                status=s.status,
                comment=s.comment,
                user_email=u.email,
                user_full_name=u.full_name,
                team_id=u.team_id,
                team_name=u.team.name if u.team else None,
            )
        )
    return out


@router.patch("/org/{shift_id}", response_model=ShiftRead)
def manager_update_shift(
    shift_id: int,
    body: ShiftUpdate,
    db: Session = Depends(get_db),
    viewer: User = Depends(require_roles(UserRole.manager, UserRole.admin)),
):
    shift = db.query(Shift).join(User).filter(Shift.id == shift_id).first()
    if not shift or shift.user.organization_id != viewer.organization_id:
        raise HTTPException(status_code=404, detail="Смена не найдена")
    data = body.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(shift, k, v)
    if shift.plan_end <= shift.plan_start:
        raise HTTPException(status_code=400, detail="Конец смены должен быть позже начала")
    db.commit()
    db.refresh(shift)
    return shift


@router.get("/summary", response_model=dict)
def workload_summary(
    from_date: date,
    to_date: date,
    team_id: int | None = None,
    db: Session = Depends(get_db),
    viewer: User = Depends(require_roles(UserRole.manager, UserRole.admin)),
):
    """Количество смен по дням в организации (нагрузка)."""
    q = (
        db.query(Shift)
        .join(User)
        .filter(
            User.organization_id == viewer.organization_id,
            Shift.work_date >= from_date,
            Shift.work_date <= to_date,
        )
    )
    if team_id is not None:
        q = q.filter(User.team_id == team_id)
    shifts = q.all()
    by_day: dict[str, int] = {}
    for s in shifts:
        key = s.work_date.isoformat()
        by_day[key] = by_day.get(key, 0) + 1
    return {"from": from_date.isoformat(), "to": to_date.isoformat(), "shifts_per_day": by_day}
