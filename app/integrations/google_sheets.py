"""
Заготовка интеграции с Google Sheets.

Для продакшена: сервисный аккаунт Google + google-api-python-client,
запись CSV или прямой append в таблицу по расписанию или по кнопке.
"""

from fastapi import APIRouter, Depends

from app.deps import require_roles
from app.models import User, UserRole

router = APIRouter(prefix="/api/integrations", tags=["integrations"])


@router.get("/google-sheets/status")
def sheets_status(_: User = Depends(require_roles(UserRole.admin, UserRole.manager))):
    return {
        "enabled": False,
        "hint": "Подключите google-api-python-client и credentials JSON; используйте /api/export/csv как промежуточный формат.",
    }
