"""근무 규칙 조회·수정"""
from fastapi import APIRouter, Depends
from ..database import get_db, db_rules
from ..deps import get_current_admin
from ..schemas import RulesOut, RulesUpdate
from ..config import settings

router = APIRouter(prefix="/rules", tags=["규칙"])


@router.get("", response_model=RulesOut)
def get_rules():
    db = get_db()
    res = db_rules(db).execute()
    if not res.data:
        return RulesOut()
    r = res.data[0]
    return RulesOut(
        daily_d=r["daily_d"], daily_e=r["daily_e"],
        daily_n=r["daily_n"], daily_m=r["daily_m"],
        max_n_per_month=r["max_n_per_month"],
        max_consecutive_n=r["max_consecutive_n"],
        off_after_2n=r["off_after_2n"],
        max_consecutive_work=r["max_consecutive_work"],
        min_weekly_off=r["min_weekly_off"],
        ban_reverse_order=r["ban_reverse_order"],
        min_chief_per_shift=r["min_chief_per_shift"],
        min_senior_per_shift=r["min_senior_per_shift"],
        pregnant_poff_interval=r["pregnant_poff_interval"],
        menstrual_leave=r["menstrual_leave"],
        sleep_n_monthly=r["sleep_n_monthly"],
        sleep_n_bimonthly=r["sleep_n_bimonthly"],
        public_holidays=r.get("public_holidays", []),
    )


@router.put("", response_model=RulesOut)
def update_rules(body: RulesUpdate, _: dict = Depends(get_current_admin)):
    db = get_db()
    data = body.model_dump()
    data["department_id"] = settings.department_id

    res = db_rules(db).execute()
    if res.data:
        saved = db_rules(db).update(data).execute()
    else:
        saved = db.table("rules").insert(data).execute()

    r = saved.data[0]
    return RulesOut(**{k: r[k] for k in body.model_fields if k in r})
