from datetime import date, time

from pydantic import BaseModel, Field

from app.models import ShiftStatus, UserRole


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenPayload(BaseModel):
    sub: str | None = None


class UserCreate(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    full_name: str
    password: str = Field(min_length=4)
    organization_id: int
    team_id: int | None = None
    role: UserRole = UserRole.employee


class UserRead(BaseModel):
    id: int
    email: str
    full_name: str
    organization_id: int
    team_id: int | None
    role: UserRole
    is_active: bool
    is_approved: bool

    model_config = {"from_attributes": True}


class RegisterResponse(BaseModel):
    message: str


class PendingUserRead(BaseModel):
    """Сотрудник, ожидающий подтверждения после саморегистрации."""

    id: int
    email: str
    full_name: str
    team_id: int | None
    team_name: str | None = None
    role: UserRole


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    password: str


class RegisterRequest(BaseModel):
    """Самостоятельная регистрация — всегда роль «сотрудник»."""

    email: str = Field(min_length=3, max_length=255)
    full_name: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=4)
    organization_id: int
    team_id: int | None = None


class ShiftCreate(BaseModel):
    work_date: date
    plan_start: time
    plan_end: time
    comment: str | None = None


class ShiftUpdate(BaseModel):
    plan_start: time | None = None
    plan_end: time | None = None
    fact_start: time | None = None
    fact_end: time | None = None
    status: ShiftStatus | None = None
    comment: str | None = None


class ShiftRead(BaseModel):
    id: int
    user_id: int
    work_date: date
    plan_start: time
    plan_end: time
    fact_start: time | None
    fact_end: time | None
    status: ShiftStatus
    comment: str | None

    model_config = {"from_attributes": True}


class ShiftReadWithUser(ShiftRead):
    user_email: str
    user_full_name: str


class OrganizationRead(BaseModel):
    id: int
    name: str

    model_config = {"from_attributes": True}


class TeamRead(BaseModel):
    id: int
    organization_id: int
    parent_id: int | None
    name: str

    model_config = {"from_attributes": True}
