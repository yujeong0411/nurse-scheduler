"""근무 기간·마감일 설정"""
from fastapi import APIRouter, Depends
from ..database import get_db, db_periods, get_active_period
from ..deps import get_current_admin
from ..schemas import SettingsOut, SettingsUpdate
from ..config import settings
from typing import Any

router = APIRouter(prefix="/settings", tags=["설정"])


def _get_department_name(db) -> str | None:
    try:
        res = db.table("departments").select("name").eq("id", settings.department_id).single().execute()
        return res.data.get("name") if res.data else None
    except Exception:
        return None


@router.get("", response_model=SettingsOut)
def get_settings():
    """인증 불필요 — 간호사 화면에서 활성 기간 조회"""
    db = get_db()
    res = db_periods(db).select("*").execute()
    active = next((p for p in res.data if p.get("is_active")), None)
    dept_name = _get_department_name(db)
    if not active:
        return SettingsOut(department_name=dept_name)
    return SettingsOut(
        period_id=active["id"],
        start_date=active["start_date"],
        deadline=active.get("deadline"),
        department_name=dept_name,
    )


@router.get("/periods")
def list_periods(_: dict = Depends(get_current_admin)) -> list[dict[str, Any]]:
    """모든 기간 목록 반환 (최신순, is_active 포함)"""
    db = get_db()
    res = db_periods(db).order("start_date", desc=True).execute()
    return [
        {
            "id": p["id"],
            "start_date": p["start_date"],
            "deadline": p.get("deadline"),
            "is_active": p.get("is_active", False),
        }
        for p in res.data
    ]


@router.put("", response_model=SettingsOut)
def update_settings(body: SettingsUpdate, _: dict = Depends(get_current_admin)):
    db = get_db()
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


@router.put("/{period_id}/activate")
def activate_period(period_id: str, _: dict = Depends(get_current_admin)):
    """해당 기간을 활성화 (기존 활성 기간은 비활성화)"""
    db = get_db()
    # 모든 기간 비활성화 후 해당 기간만 활성화
    db_periods(db).update({"is_active": False}).execute()
    db.table("periods").update({"is_active": True}).eq("id", period_id).execute()
    return {"ok": True}


@router.delete("/{period_id}")
def delete_period(period_id: str, _: dict = Depends(get_current_admin)):
    """기간 삭제 (신청·근무표 CASCADE 삭제)"""
    db = get_db()
    db.table("periods").delete().eq("id", period_id).execute()
    return {"ok": True}


@router.get("/{period_id}", response_model=SettingsOut)
def get_period_by_id(period_id: str, _: dict = Depends(get_current_admin)):
    """특정 period 조회"""
    from ..database import get_period_by_id as _get
    db = get_db()
    p = _get(db, period_id)
    if not p:
        from fastapi import HTTPException
        raise HTTPException(404)
    return SettingsOut(period_id=p["id"], start_date=p["start_date"], deadline=p.get("deadline"))
