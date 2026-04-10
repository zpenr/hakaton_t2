import csv
import io
from datetime import date

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import require_roles
from app.models import Shift, User, UserRole

router = APIRouter(prefix="/api/export", tags=["export"])


@router.get("/csv")
def export_csv(
    from_date: date,
    to_date: date,
    team_id: int | None = None,
    db: Session = Depends(get_db),
    viewer: User = Depends(require_roles(UserRole.manager, UserRole.admin)),
):
    """Табличная выгрузка: день, сотрудник, план/факт начало и конец."""
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
    shifts = q.order_by(Shift.work_date, User.full_name).all()
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")
    w.writerow(
        [
            "Дата",
            "Сотрудник",
            "Email",
            "План_начало",
            "План_конец",
            "Факт_начало",
            "Факт_конец",
            "Статус",
            "Комментарий",
        ]
    )
    for s in shifts:
        u = s.user
        w.writerow(
            [
                s.work_date.isoformat(),
                u.full_name,
                u.email,
                s.plan_start.strftime("%H:%M"),
                s.plan_end.strftime("%H:%M"),
                s.fact_start.strftime("%H:%M") if s.fact_start else "",
                s.fact_end.strftime("%H:%M") if s.fact_end else "",
                s.status.value,
                s.comment or "",
            ]
        )
    return Response(
        content=buf.getvalue().encode("utf-8-sig"),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="schedule_{from_date}_{to_date}.csv"'
        },
    )
