import enum
from datetime import date, time

from sqlalchemy import (
    Boolean,
    Date,
    Enum as SAEnum,
    ForeignKey,
    Integer,
    String,
    Text,
    Time,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class UserRole(str, enum.Enum):
    admin = "admin"
    manager = "manager"
    employee = "employee"


class ShiftStatus(str, enum.Enum):
    draft = "draft"
    submitted = "submitted"
    confirmed = "confirmed"


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    teams: Mapped[list["Team"]] = relationship(back_populates="organization")
    users: Mapped[list["User"]] = relationship(back_populates="organization")


class Team(Base):
    __tablename__ = "teams"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), nullable=False)
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("teams.id"), nullable=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    organization: Mapped["Organization"] = relationship(back_populates="teams")
    parent: Mapped["Team | None"] = relationship(
        "Team",
        remote_side="Team.id",
        back_populates="children",
    )
    children: Mapped[list["Team"]] = relationship("Team", back_populates="parent")
    users: Mapped[list["User"]] = relationship(back_populates="team")


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), nullable=False)
    team_id: Mapped[int | None] = mapped_column(ForeignKey("teams.id"), nullable=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        SAEnum(UserRole, values_callable=lambda e: [i.value for i in e], native_enum=False),
        nullable=False,
        default=UserRole.employee,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    # Саморегистрация: False до подтверждения руководителем/админом; пользователи из админки — True
    is_approved: Mapped[bool] = mapped_column(Boolean, default=True)

    organization: Mapped["Organization"] = relationship(back_populates="users")
    team: Mapped["Team | None"] = relationship(back_populates="users")
    shifts: Mapped[list["Shift"]] = relationship(back_populates="user")


class Shift(Base):
    __tablename__ = "shifts"
    __table_args__ = (UniqueConstraint("user_id", "work_date", name="uq_shift_user_date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    work_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    plan_start: Mapped[time] = mapped_column(Time, nullable=False)
    plan_end: Mapped[time] = mapped_column(Time, nullable=False)
    fact_start: Mapped[time | None] = mapped_column(Time, nullable=True)
    fact_end: Mapped[time | None] = mapped_column(Time, nullable=True)
    status: Mapped[ShiftStatus] = mapped_column(
        SAEnum(ShiftStatus, values_callable=lambda e: [i.value for i in e], native_enum=False),
        default=ShiftStatus.draft,
    )
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)

    user: Mapped["User"] = relationship(back_populates="shifts")


class GoogleSheetsCredential(Base):
    __tablename__ = "google_sheets_credentials"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), unique=True, nullable=False)
    service_account_json: Mapped[str] = mapped_column(Text, nullable=False)
