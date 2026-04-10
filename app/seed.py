from sqlalchemy import func
from sqlalchemy.orm import Session

from app.auth_utils import hash_password, verify_password
from app.models import Organization, Shift, ShiftStatus, Team, User, UserRole

# Демо-логины (пароли подтягиваются при старте, если хеш в БД не совпадает)
DEMO_ACCOUNTS: tuple[tuple[str, str], ...] = (
    ("admin@demo.local", "admin123"),
    ("manager@demo.local", "manager123"),
    ("employee@demo.local", "employee123"),
)


def repair_demo_passwords(db: Session) -> None:
    """Если пароль демо-пользователя не проходит проверку — перезаписываем хеш (после смены bcrypt/passlib и т.п.)."""
    changed = False
    for email, plain in DEMO_ACCOUNTS:
        u = db.query(User).filter(func.lower(User.email) == email.lower()).first()
        if u and not verify_password(plain, u.hashed_password):
            u.hashed_password = hash_password(plain)
            changed = True
    if changed:
        db.commit()


def seed_if_empty(db: Session) -> None:
    if db.query(User).first():
        return
    org = Organization(name="Демо организация")
    db.add(org)
    db.flush()

    dept = Team(organization_id=org.id, name="Подразделение продаж", parent_id=None)
    db.add(dept)
    db.flush()
    team = Team(organization_id=org.id, name="Команда B2B", parent_id=dept.id)
    db.add(team)
    db.flush()

    users = [
        User(
            organization_id=org.id,
            team_id=None,
            email="admin@demo.local",
            full_name="Администратор",
            hashed_password=hash_password("admin123"),
            role=UserRole.admin,
            is_approved=True,
        ),
        User(
            organization_id=org.id,
            team_id=dept.id,
            email="manager@demo.local",
            full_name="Руководитель подразделения",
            hashed_password=hash_password("manager123"),
            role=UserRole.manager,
            is_approved=True,
        ),
        User(
            organization_id=org.id,
            team_id=team.id,
            email="employee@demo.local",
            full_name="Иван Сотрудников",
            hashed_password=hash_password("employee123"),
            role=UserRole.employee,
            is_approved=True,
        ),
    ]
    for u in users:
        db.add(u)
    db.commit()

    emp = db.query(User).filter(User.email == "employee@demo.local").first()
    if emp:
        from datetime import date, timedelta, time

        d0 = date.today()
        s1 = Shift(
            user_id=emp.id,
            work_date=d0 + timedelta(days=1),
            plan_start=time(9, 0),
            plan_end=time(18, 0),
            status=ShiftStatus.draft,
        )
        db.add(s1)
        db.commit()
