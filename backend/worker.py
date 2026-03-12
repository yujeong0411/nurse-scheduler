"""ProcessPoolExecutor로 solve_schedule 비동기 실행"""
import asyncio
import sys
import os
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone

_executor = ProcessPoolExecutor(max_workers=1)


def _run_solver_sync(
    nurses_data: list[dict],
    requests_data: list[dict],
    rules_data: dict,
    start_date_str: str,
    timeout_seconds: int,
) -> dict:
    """별도 프로세스에서 실행 — engine/ 직접 호출"""
    # 프로세스 내에서 engine 경로를 sys.path에 추가
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if root not in sys.path:
        sys.path.insert(0, root)

    from engine.models import Nurse, Request, Rules
    from engine.solver import solve_schedule
    from datetime import date

    nurses   = [Nurse.from_dict(n)   for n in nurses_data]
    requests = [Request.from_dict(r) for r in requests_data]
    rules    = Rules.from_dict(rules_data)
    start_date = date.fromisoformat(start_date_str)

    schedule = solve_schedule(nurses, requests, rules, start_date, timeout_seconds)

    # 직렬화 가능한 dict로 변환: {nurse_id(str): {day(str): shift}}
    result: dict = {}
    for nid, days in schedule.schedule_data.items():
        result[str(nid)] = {str(d): s for d, s in days.items()}
    return result


async def run_solver_job(job_id: str, period_id: str, db) -> None:
    """BackgroundTasks에서 호출"""
    from .database import get_db

    if db is None:
        db = get_db()

    now_iso = datetime.now(timezone.utc).isoformat()
    db.table("solver_jobs").update({"status": "running", "started_at": now_iso}).eq("id", job_id).execute()

    try:
        # 입력 데이터 로드
        nurses_res  = db.table("nurses").select("*").eq("department_id", _get_department_id(db, period_id)).order("sort_order").execute()
        req_res     = db.table("requests").select("*").eq("period_id", period_id).execute()
        rules_res   = db.table("rules").select("*").execute()
        period_res  = db.table("periods").select("*").eq("id", period_id).single().execute()

        nurses_data   = nurses_res.data
        requests_data = _convert_requests(req_res.data, nurses_data)
        rules_data    = _convert_rules(rules_res.data[0] if rules_res.data else {})
        start_date_str = period_res.data["start_date"]

        loop   = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            _executor,
            _run_solver_sync,
            nurses_data, requests_data, rules_data, start_date_str, 180,
        )

        # 결과 저장
        done_iso = datetime.now(timezone.utc).isoformat()
        sched = db.table("schedules").insert({
            "period_id": period_id,
            "job_id": job_id,
            "schedule_data": result,
        }).execute()
        schedule_id = sched.data[0]["id"]

        db.table("solver_jobs").update({
            "status": "done",
            "finished_at": done_iso,
        }).eq("id", job_id).execute()

        # schedule_id를 job에 저장해서 폴링 응답에 포함
        db.table("solver_jobs").update({"schedule_id": schedule_id}).eq("id", job_id).execute()

    except Exception as e:
        done_iso = datetime.now(timezone.utc).isoformat()
        db.table("solver_jobs").update({
            "status": "failed",
            "finished_at": done_iso,
            "error_msg": str(e),
        }).eq("id", job_id).execute()


def _get_department_id(db, period_id: str) -> str:
    res = db.table("periods").select("*").eq("id", period_id).single().execute()
    return res.data["department_id"]


def _convert_requests(raw_requests: list[dict], nurses: list[dict]) -> list[dict]:
    """DB requests → engine Request.from_dict 형식 (nurse_id를 int index로 매핑)"""
    # nurse UUID → int id 매핑 (engine은 int id를 사용)
    uuid_to_int = {n["id"]: i for i, n in enumerate(nurses)}
    result = []
    for r in raw_requests:
        nid = uuid_to_int.get(r["nurse_id"])
        if nid is None:
            continue
        result.append({
            "nurse_id": nid,
            "day": r["day"],
            "code": r["code"],
            "is_or": r.get("is_or", False),
        })
    return result


def _convert_rules(raw: dict) -> dict:
    """DB rules 행 → engine Rules.from_dict 형식 (snake_case 통일)"""
    return {
        "daily_D": raw.get("daily_d", 7),
        "daily_E": raw.get("daily_e", 8),
        "daily_N": raw.get("daily_n", 7),
        "daily_M": raw.get("daily_m", 1),
        "max_N_per_month":      raw.get("max_n_per_month", 6),
        "max_consecutive_N":    raw.get("max_consecutive_n", 3),
        "off_after_2N":         raw.get("off_after_2n", 2),
        "max_consecutive_work": raw.get("max_consecutive_work", 5),
        "min_weekly_off":       raw.get("min_weekly_off", 2),
        "ban_reverse_order":    raw.get("ban_reverse_order", True),
        "min_chief_per_shift":  raw.get("min_chief_per_shift", 1),
        "min_senior_per_shift": raw.get("min_senior_per_shift", 2),
        "pregnant_poff_interval": raw.get("pregnant_poff_interval", 4),
        "menstrual_leave":      raw.get("menstrual_leave", True),
        "sleep_N_monthly":      raw.get("sleep_n_monthly", 7),
        "sleep_N_bimonthly":    raw.get("sleep_n_bimonthly", 11),
        "public_holidays":      raw.get("public_holidays", []),
    }
