from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import require_roles
from app.models import Shift, User, UserRole

router = APIRouter(prefix="/api/reports", tags=["reports"])


def _minutes(t) -> int:
    return t.hour * 60 + t.minute


@router.get("/plan-fact")
def plan_fact_report(
    from_date: date,
    to_date: date,
    team_id: int | None = None,
    db: Session = Depends(get_db),
    viewer: User = Depends(require_roles(UserRole.manager, UserRole.admin)),
):
    """Сводка по минутам план vs факт по сотрудникам за период."""
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
    by_user: dict[int, dict] = {}
    for s in shifts:
        uid = s.user_id
        if uid not in by_user:
            by_user[uid] = {
                "user_id": uid,
                "full_name": s.user.full_name,
                "plan_minutes": 0,
                "fact_minutes": 0,
                "shifts_count": 0,
            }
        by_user[uid]["shifts_count"] += 1
        plan_dur = _minutes(s.plan_end) - _minutes(s.plan_start)
        if plan_dur < 0:
            plan_dur += 24 * 60
        by_user[uid]["plan_minutes"] += plan_dur
        if s.fact_start and s.fact_end:
            fd = _minutes(s.fact_end) - _minutes(s.fact_start)
            if fd < 0:
                fd += 24 * 60
            by_user[uid]["fact_minutes"] += fd
    rows = list(by_user.values())
    rows.sort(key=lambda r: r["full_name"])
    return {"from": from_date.isoformat(), "to": to_date.isoformat(), "rows": rows}
