"""근무 기간·마감일 설정"""
from fastapi import APIRouter, Depends
from ..database import get_db, db_periods, get_active_period
from ..deps import get_current_admin
from ..schemas import SettingsOut, SettingsUpdate
from ..config import settings

router = APIRouter(prefix="/settings", tags=["설정"])


@router.get("", response_model=SettingsOut)
def get_settings():
    """인증 불필요 — 랜딩 페이지에서 기간 표시용"""
    db = get_db()
    period = get_active_period(db)
    if not period:
        return SettingsOut()
    return SettingsOut(
        period_id=period["id"],
        start_date=period["start_date"],
        deadline=period.get("deadline"),
    )


@router.put("", response_model=SettingsOut)
def update_settings(body: SettingsUpdate, _: dict = Depends(get_current_admin)):
    db = get_db()
    # 같은 start_date가 있으면 update, 없으면 insert
    existing = db_periods(db).eq("start_date", body.start_date).execute()
    data = {
        "department_id": settings.department_id,
        "start_date": body.start_date,
        "deadline": body.deadline,
    }
    if existing.data:
        res = db_periods(db).update({"deadline": body.deadline}).eq("start_date", body.start_date).execute()
        period = res.data[0]
    else:
        res = db.table("periods").insert(data).execute()
        period = res.data[0]

    return SettingsOut(
        period_id=period["id"],
        start_date=period["start_date"],
        deadline=period.get("deadline"),
    )
