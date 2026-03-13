"""근무표 xlsx 스트리밍 다운로드"""
import io
import os
import sys
import tempfile
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from ..database import get_db, db_nurses, db_rules, get_period_by_id
from ..deps import get_current_admin
from ..worker import _convert_rules

router = APIRouter(prefix="/schedule", tags=["내보내기"])

_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _root not in sys.path:
    sys.path.insert(0, _root)


@router.get("/{schedule_id}/export")
def export_schedule_excel(schedule_id: str, _: dict = Depends(get_current_admin)):
    from engine.models import Nurse, Rules, Schedule, Request
    from engine.excel_io import export_schedule
    from datetime import date

    db = get_db()
    sched_res = db.table("schedules").select("*").eq("id", schedule_id).single().execute()
    if not sched_res.data:
        raise HTTPException(404)
    sched = sched_res.data

    period = get_period_by_id(db, sched["period_id"])
    rules_res = db_rules(db).execute()
    nurses_res = db_nurses(db).order("sort_order").execute()

    rules = Rules.from_dict(_convert_rules(rules_res.data[0] if rules_res.data else {}))
    nurses_all = nurses_res.data
    uuid_to_int = {n["id"]: i for i, n in enumerate(nurses_all)}

    nurses = [
        Nurse(
            id=i, name=n["name"], role=n.get("role",""), grade=n.get("grade",""),
            is_pregnant=n.get("is_pregnant",False), is_male=n.get("is_male",False),
            is_4day_week=n.get("is_4day_week",False),
            fixed_weekly_off=n.get("fixed_weekly_off"),
            vacation_days=n.get("vacation_days",0),
            prev_month_N=n.get("prev_month_n",0),
            pending_sleep=n.get("pending_sleep",False),
            menstrual_used=n.get("menstrual_used",False),
            prev_tail_shifts=n.get("prev_tail_shifts",[]),
        )
        for i, n in enumerate(nurses_all)
    ]

    raw_data = sched.get("schedule_data", {})
    int_data = {
        uuid_to_int[uuid]: {int(d): s for d, s in days.items()}
        for uuid, days in raw_data.items()
        if uuid in uuid_to_int
    }

    req_res = db.table("requests").select("*").eq("period_id", sched["period_id"]).execute()
    requests = [
        Request(nurse_id=uuid_to_int[r["nurse_id"]], day=r["day"], code=r["code"], is_or=r.get("is_or",False))
        for r in req_res.data if r["nurse_id"] in uuid_to_int
    ]

    schedule = Schedule(
        start_date=date.fromisoformat(period["start_date"]),
        nurses=nurses, rules=rules, requests=requests,
        schedule_data=int_data,
    )

    # export_schedule은 filepath를 받으므로 tempfile 우회
    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
        tmp_path = tmp.name
    try:
        export_schedule(schedule, rules, tmp_path)
        with open(tmp_path, "rb") as f:
            content = f.read()
    finally:
        os.unlink(tmp_path)

    from urllib.parse import quote
    filename = f"근무표_{period['start_date']}.xlsx"
    encoded = quote(filename, safe='')
    return StreamingResponse(
        io.BytesIO(content),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{encoded}"},
    )
