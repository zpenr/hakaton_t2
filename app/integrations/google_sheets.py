from __future__ import annotations

import json
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import require_roles
from app.models import GoogleSheetsCredential, Shift, User, UserRole

router = APIRouter(prefix="/api/integrations", tags=["integrations"])

SHEETS_SCOPE = "https://www.googleapis.com/auth/spreadsheets"


class GoogleSheetsKeyPayload(BaseModel):
    service_account_json: str


def _get_creds(db: Session, organization_id: int) -> Credentials:
    row = (
        db.query(GoogleSheetsCredential)
        .filter(GoogleSheetsCredential.organization_id == organization_id)
        .first()
    )
    if not row:
        raise HTTPException(
            status_code=400,
            detail="Google Sheets не настроен. Загрузите JSON-ключ сервисного аккаунта в интерфейсе.",
        )
    try:
        info = json.loads(row.service_account_json)
        return Credentials.from_service_account_info(info, scopes=[SHEETS_SCOPE])
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Некорректный JSON ключа Google: {exc}") from exc


def _get_sheets_client(db: Session, organization_id: int):
    creds = _get_creds(db, organization_id)
    return build("sheets", "v4", credentials=creds, cache_discovery=False)


def _ensure_sheet(service, spreadsheet_id: str, title: str) -> int:
    try:
        meta = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
    except HttpError as exc:
        _raise_google_http_error(exc)
    for sh in meta.get("sheets", []):
        props = sh.get("properties", {})
        if props.get("title") == title:
            return int(props.get("sheetId"))
    req = {"requests": [{"addSheet": {"properties": {"title": title}}}]}
    try:
        res = service.spreadsheets().batchUpdate(spreadsheetId=spreadsheet_id, body=req).execute()
    except HttpError as exc:
        _raise_google_http_error(exc)
    replies = res.get("replies", [])
    if not replies:
        raise HTTPException(status_code=500, detail="Не удалось создать лист")
    return int(replies[0]["addSheet"]["properties"]["sheetId"])


def _raise_google_http_error(exc: HttpError) -> None:
    message = str(exc)
    lower = message.lower()
    if "service_disabled" in lower or "has not been used in project" in lower:
        raise HTTPException(
            status_code=400,
            detail=(
                "Google Sheets API отключён для проекта сервисного аккаунта. "
                "Откройте Google Cloud Console, включите Google Sheets API для этого проекта "
                "и повторите попытку через 1-5 минут."
            ),
        ) from exc
    if "requested entity was not found" in lower or "404" in lower:
        raise HTTPException(
            status_code=400,
            detail="Таблица не найдена. Проверьте Spreadsheet ID в URL Google Sheets.",
        ) from exc
    if "permission" in lower or "forbidden" in lower or "403" in lower:
        raise HTTPException(
            status_code=400,
            detail=(
                "Нет доступа к Google таблице. Расшарьте таблицу на client_email из JSON ключа "
                "с правами Editor и повторите попытку."
            ),
        ) from exc
    raise HTTPException(status_code=502, detail=f"Ошибка Google Sheets: {message}") from exc


@router.get("/google-sheets/status")
def sheets_status(
    db: Session = Depends(get_db),
    viewer: User = Depends(require_roles(UserRole.admin, UserRole.manager)),
):
    configured = (
        db.query(GoogleSheetsCredential)
        .filter(GoogleSheetsCredential.organization_id == viewer.organization_id)
        .first()
        is not None
    )
    return {
        "enabled": configured,
        "configured": configured,
        "hint": "Загрузите JSON-ключ сервисного аккаунта через GUI, затем укажите Spreadsheet ID при выгрузке.",
    }


@router.post("/google-sheets/key")
def upsert_google_sheets_key(
    body: GoogleSheetsKeyPayload,
    db: Session = Depends(get_db),
    viewer: User = Depends(require_roles(UserRole.admin, UserRole.manager)),
):
    try:
        parsed = json.loads(body.service_account_json)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Невалидный JSON: {exc}") from exc
    if "client_email" not in parsed or "private_key" not in parsed:
        raise HTTPException(status_code=400, detail="В JSON отсутствуют обязательные поля client_email/private_key")
    row = (
        db.query(GoogleSheetsCredential)
        .filter(GoogleSheetsCredential.organization_id == viewer.organization_id)
        .first()
    )
    normalized = json.dumps(parsed, ensure_ascii=False)
    if row:
        row.service_account_json = normalized
    else:
        row = GoogleSheetsCredential(
            organization_id=viewer.organization_id,
            service_account_json=normalized,
        )
        db.add(row)
    db.commit()
    return {"message": "JSON-ключ Google Sheets сохранён для вашей организации."}


@router.post("/google-sheets/export")
def export_to_google_sheets(
    from_date: date,
    to_date: date,
    spreadsheet_id: str,
    sheet_name: str | None = None,
    team_id: int | None = None,
    db: Session = Depends(get_db),
    viewer: User = Depends(require_roles(UserRole.manager, UserRole.admin)),
):
    """
    Создаёт (если нет) и обновляет лист Google Sheets за период.

    - spreadsheet_id: ID таблицы (из URL Google Sheets).
    - sheet_name: имя листа. По умолчанию: \"График YYYY-MM-DD..YYYY-MM-DD\".
    - team_id: фильтр по подразделению (как в менеджерском интерфейсе).
    """
    sid = spreadsheet_id.strip()
    if not sid:
        raise HTTPException(status_code=400, detail="Не указан spreadsheet_id")
    title = (sheet_name or f"График {from_date.isoformat()}..{to_date.isoformat()}").strip()

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

    values: list[list[str]] = [
        [
            "Дата",
            "Сотрудник",
            "Email",
            "Подразделение",
            "План_начало",
            "План_конец",
            "Факт_начало",
            "Факт_конец",
            "Статус",
            "Комментарий",
        ]
    ]
    for s in shifts:
        u = s.user
        team = u.team.name if u.team else ""
        values.append(
            [
                s.work_date.isoformat(),
                u.full_name,
                u.email,
                team,
                s.plan_start.strftime("%H:%M"),
                s.plan_end.strftime("%H:%M"),
                s.fact_start.strftime("%H:%M") if s.fact_start else "",
                s.fact_end.strftime("%H:%M") if s.fact_end else "",
                s.status.value,
                s.comment or "",
            ]
        )

    service = _get_sheets_client(db, viewer.organization_id)
    _ensure_sheet(service, sid, title)

    # очищаем прошлые данные и пишем заново с A1
    try:
        service.spreadsheets().values().clear(
            spreadsheetId=sid,
            range=f"{title}!A1:Z",
            body={},
        ).execute()
        service.spreadsheets().values().update(
            spreadsheetId=sid,
            range=f"{title}!A1",
            valueInputOption="USER_ENTERED",
            body={"values": values},
        ).execute()
    except HttpError as exc:
        _raise_google_http_error(exc)

    return {
        "spreadsheet_id": sid,
        "sheet_name": title,
        "rows_written": len(values),
        "message": "Выгрузка выполнена (лист создан/обновлён).",
    }
