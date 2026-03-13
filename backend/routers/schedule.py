"""근무표 생성·조회·셀 수정·평가"""
import sys
import os
from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from datetime import datetime, timezone
from ..database import get_db, db_nurses, db_rules, get_period_by_id
from ..deps import get_current_admin
from ..schemas import (
    GenerateRequest, JobStatusOut, CellUpdate, CellUpdateResult,
    ScheduleOut, EvaluateOut, NurseOut,
)
from ..config import settings
from ..worker import run_solver_job, _convert_rules

router = APIRouter(prefix="/schedule", tags=["근무표"])

# engine 경로 등록
_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _root not in sys.path:
    sys.path.insert(0, _root)


@router.post("/generate", response_model=JobStatusOut)
async def generate_schedule(
    body: GenerateRequest,
    background_tasks: BackgroundTasks,
    _: dict = Depends(get_current_admin),
):
    db = get_db()
    period = get_period_by_id(db, body.period_id)
    if not period:
        raise HTTPException(404, "기간을 찾을 수 없습니다.")

    # job 생성
    job_res = db.table("solver_jobs").insert({
        "period_id": body.period_id,
        "status": "pending",
    }).execute()
    job_id = job_res.data[0]["id"]

    background_tasks.add_task(run_solver_job, job_id, body.period_id, db)
    return JobStatusOut(job_id=job_id, status="pending")


@router.get("/job/{job_id}", response_model=JobStatusOut)
def get_job_status(job_id: str, _: dict = Depends(get_current_admin)):
    db = get_db()
    res = db.table("solver_jobs").select("*").eq("id", job_id).single().execute()
    if not res.data:
        raise HTTPException(404)
    job = res.data
    schedule_id = job.get("schedule_id")
    # schedule_id가 jobs 테이블에 없으면 schedules에서 찾기
    if not schedule_id and job["status"] == "done":
        s = db.table("schedules").select("*").eq("job_id", job_id).order("created_at", desc=True).limit(1).execute()
        if s.data:
            schedule_id = s.data[0]["id"]
    return JobStatusOut(
        job_id=job_id,
        status=job["status"],
        schedule_id=schedule_id,
        error_msg=job.get("error_msg"),
    )


@router.get("/period/{period_id}", response_model=ScheduleOut)
def get_schedule_by_period(period_id: str, _: dict = Depends(get_current_admin)):
    """기간의 최신 근무표 조회"""
    db = get_db()
    res = db.table("schedules").select("*").eq("period_id", period_id).order("created_at", desc=True).limit(1).execute()
    if not res.data:
        raise HTTPException(404)
    sched = res.data[0]

    nurses_res = db_nurses(db).order("sort_order").execute()
    nurses = [
        NurseOut(
            id=n["id"], name=n["name"], role=n.get("role", ""),
            grade=n.get("grade", ""), is_pregnant=n.get("is_pregnant", False),
            is_male=n.get("is_male", False), is_4day_week=n.get("is_4day_week", False),
            fixed_weekly_off=n.get("fixed_weekly_off"),
            vacation_days=n.get("vacation_days", 0),
            prev_month_n=n.get("prev_month_n", 0),
            pending_sleep=n.get("pending_sleep", False),
            menstrual_used=n.get("menstrual_used", False),
            prev_tail_shifts=n.get("prev_tail_shifts", []),
            note=n.get("note", ""), sort_order=n.get("sort_order", 0),
        )
        for n in nurses_res.data
    ]
    return ScheduleOut(
        id=sched["id"],
        period_id=sched["period_id"],
        schedule_data=sched.get("schedule_data", {}),
        nurses=nurses,
        score=sched.get("score"),
        grade=sched.get("grade"),
        eval_details=sched.get("eval_details", {}),
    )


@router.get("/{schedule_id}", response_model=ScheduleOut)
def get_schedule(schedule_id: str, _: dict = Depends(get_current_admin)):
    db = get_db()
    res = db.table("schedules").select("*").eq("id", schedule_id).single().execute()
    if not res.data:
        raise HTTPException(404)
    sched = res.data

    nurses_res = db_nurses(db).order("sort_order").execute()
    nurses = [
        NurseOut(
            id=n["id"], name=n["name"], role=n.get("role", ""),
            grade=n.get("grade", ""), is_pregnant=n.get("is_pregnant", False),
            is_male=n.get("is_male", False), is_4day_week=n.get("is_4day_week", False),
            fixed_weekly_off=n.get("fixed_weekly_off"),
            vacation_days=n.get("vacation_days", 0),
            prev_month_n=n.get("prev_month_n", 0),
            pending_sleep=n.get("pending_sleep", False),
            menstrual_used=n.get("menstrual_used", False),
            prev_tail_shifts=n.get("prev_tail_shifts", []),
            note=n.get("note", ""), sort_order=n.get("sort_order", 0),
        )
        for n in nurses_res.data
    ]

    return ScheduleOut(
        id=sched["id"],
        period_id=sched["period_id"],
        schedule_data=sched.get("schedule_data", {}),
        nurses=nurses,
        score=sched.get("score"),
        grade=sched.get("grade"),
        eval_details=sched.get("eval_details", {}),
    )


@router.patch("/{schedule_id}/cell", response_model=CellUpdateResult)
def update_cell(schedule_id: str, body: CellUpdate, _: dict = Depends(get_current_admin)):
    """셀 수동 수정 + validate_change() 검사"""
    from engine.models import Nurse, Rules, Schedule
    from engine.validator import validate_change
    from datetime import date

    db = get_db()
    sched_res = db.table("schedules").select("*").eq("id", schedule_id).single().execute()
    if not sched_res.data:
        raise HTTPException(404)
    sched = sched_res.data

    period = get_period_by_id(db, sched["period_id"])
    rules_res = db_rules(db).execute()
    nurse_res = db_nurses(db).eq("id", body.nurse_id).single().execute()

    if not nurse_res.data:
        raise HTTPException(404, "간호사를 찾을 수 없습니다.")

    n = nurse_res.data
    nurses_all = db_nurses(db).order("sort_order").execute().data
    uuid_to_int = {x["id"]: i for i, x in enumerate(nurses_all)}
    nurse_int_id = uuid_to_int[body.nurse_id]

    nurse = Nurse(
        id=nurse_int_id, name=n["name"], role=n.get("role", ""),
        grade=n.get("grade", ""), is_pregnant=n.get("is_pregnant", False),
        is_male=n.get("is_male", False), is_4day_week=n.get("is_4day_week", False),
        fixed_weekly_off=n.get("fixed_weekly_off"),
        vacation_days=n.get("vacation_days", 0),
        prev_month_n=n.get("prev_month_n", 0),
        pending_sleep=n.get("pending_sleep", False),
        menstrual_used=n.get("menstrual_used", False),
        prev_tail_shifts=n.get("prev_tail_shifts", []),
    )
    rules = Rules.from_dict(_convert_rules(rules_res.data[0] if rules_res.data else {}))

    # schedule_data를 int key로 변환해서 Schedule 객체 재구성
    raw_data = sched.get("schedule_data", {})
    int_data = {}
    for uuid, days in raw_data.items():
        iid = uuid_to_int.get(uuid)
        if iid is not None:
            int_data[iid] = {int(d): s for d, s in days.items()}

    schedule = Schedule(
        start_date=date.fromisoformat(period["start_date"]),
        nurses=[],
        rules=rules,
        requests=[],
        schedule_data=int_data,
    )

    violations = validate_change(schedule, nurse, body.day, body.new_shift, rules)

    if violations and not body.force:
        return CellUpdateResult(violations=violations, saved=False)

    # 저장: schedule_data 업데이트
    raw_data.setdefault(body.nurse_id, {})[str(body.day)] = body.new_shift
    db.table("schedules").update({"schedule_data": raw_data}).eq("id", schedule_id).execute()

    return CellUpdateResult(violations=violations, saved=True)


@router.get("/{schedule_id}/evaluate", response_model=EvaluateOut)
def evaluate_schedule_endpoint(schedule_id: str, _: dict = Depends(get_current_admin)):
    from engine.models import Nurse, Rules, Schedule, Request
    from engine.evaluator import evaluate_schedule
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
        Nurse(id=i, name=n["name"], role=n.get("role",""), grade=n.get("grade",""),
              is_pregnant=n.get("is_pregnant",False), is_male=n.get("is_male",False),
              is_4day_week=n.get("is_4day_week",False),
              fixed_weekly_off=n.get("fixed_weekly_off"),
              vacation_days=n.get("vacation_days",0),
              prev_month_n=n.get("prev_month_n",0),
              pending_sleep=n.get("pending_sleep",False),
              menstrual_used=n.get("menstrual_used",False),
              prev_tail_shifts=n.get("prev_tail_shifts",[]))
        for i, n in enumerate(nurses_all)
    ]

    raw_data = sched.get("schedule_data", {})
    int_data = {
        uuid_to_int[uuid]: {int(d): s for d, s in days.items()}
        for uuid, days in raw_data.items()
        if uuid in uuid_to_int
    }

    # requests 로드
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

    result = evaluate_schedule(schedule, rules)
    return EvaluateOut(
        score=result["score"],
        grade=result["grade"],
        violation_details=result.get("violation_details", []),
        request_fulfilled=result.get("request_fulfilled", {}),
        bad_patterns=result.get("bad_patterns", {}),
        deductions=result.get("deductions", []),
    )
