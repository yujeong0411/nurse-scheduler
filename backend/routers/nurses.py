"""간호사 CRUD + 엑셀 import"""
import io
import sys
import os
import tempfile
from fastapi import APIRouter, HTTPException, UploadFile, File, Depends, Query
from ..database import get_db, db_nurses, db_rules, db_periods, get_active_period, get_period_by_id
from ..auth import hash_password
from ..deps import get_current_admin, get_current_nurse
from ..schemas import NurseCreate, NurseUpdate, NurseOut, ApplyPrevResult
from ..config import settings

router = APIRouter(prefix="/nurses", tags=["간호사"])


def _row_to_out(row: dict) -> NurseOut:
    return NurseOut(
        id=row["id"],
        name=row["name"],
        role=row.get("role", ""),
        grade=row.get("grade", ""),
        is_pregnant=row.get("is_pregnant", False),
        is_male=row.get("is_male", False),
        is_4day_week=row.get("is_4day_week", False),
        fixed_weekly_off=row.get("fixed_weekly_off"),
        vacation_days=row.get("vacation_days", 0),
        prev_month_n=row.get("prev_month_n", 0),
        pending_sleep=row.get("pending_sleep", False),
        menstrual_used=row.get("menstrual_used", False),
        prev_tail_shifts=row.get("prev_tail_shifts", []),
        note=row.get("note", ""),
        sort_order=row.get("sort_order", 0),
    )


@router.get("/me", response_model=NurseOut)
def get_my_profile(current: dict = Depends(get_current_nurse)):
    """간호사 본인 프로필 조회 (유효성 검사용)"""
    db = get_db()
    res = db_nurses(db).eq("id", current["sub"]).single().execute()
    if not res.data:
        raise HTTPException(404, "간호사를 찾을 수 없습니다.")
    return _row_to_out(res.data)


@router.get("/names")
def list_nurse_names():
    """이름+ID만 공개 (간호사 로그인 화면용, 인증 불필요)"""
    db = get_db()
    res = db_nurses(db).select("id,name,grade,role").order("sort_order").execute()
    return [{"id": r["id"], "name": r["name"], "grade": r.get("grade",""), "role": r.get("role","")} for r in res.data]


@router.get("", response_model=list[NurseOut])
def list_nurses(_: dict = Depends(get_current_admin)):
    db = get_db()
    res = db_nurses(db).order("sort_order").execute()
    return [_row_to_out(r) for r in res.data]


@router.post("", response_model=NurseOut)
def create_nurse(body: NurseCreate, _: dict = Depends(get_current_admin)):
    db = get_db()
    data = body.model_dump()
    data["department_id"] = settings.department_id
    data["pin_hash"] = hash_password("0000")
    res = db.table("nurses").insert(data).execute()
    return _row_to_out(res.data[0])


@router.put("/{nurse_id}", response_model=NurseOut)
def update_nurse(nurse_id: str, body: NurseUpdate, _: dict = Depends(get_current_admin)):
    db = get_db()
    data = body.model_dump()
    res = db_nurses(db).update(data).eq("id", nurse_id).execute()
    if not res.data:
        raise HTTPException(404, "간호사를 찾을 수 없습니다.")
    return _row_to_out(res.data[0])


@router.delete("/{nurse_id}")
def delete_nurse(nurse_id: str, _: dict = Depends(get_current_admin)):
    db = get_db()
    db_nurses(db).delete().eq("id", nurse_id).execute()
    return {"message": "삭제되었습니다."}


@router.post("/apply-prev-schedule", response_model=ApplyPrevResult)
def apply_prev_schedule(
    schedule_id: str | None = Query(default=None),
    _: dict = Depends(get_current_admin),
):
    """이전 근무표(DB)에서 prev_tail_shifts, prev_month_N, pending_sleep, menstrual_used, vacation_days 자동 계산 후 업데이트"""
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    if root not in sys.path:
        sys.path.insert(0, root)
    from engine.models import is_pair_first_month
    from datetime import date, timedelta

    db = get_db()

    # 이전 근무표 찾기
    if schedule_id:
        sched_res = db.table("schedules").select("*").eq("id", schedule_id).single().execute()
        if not sched_res.data:
            raise HTTPException(404, "이전 근무표를 찾을 수 없습니다.")
        sched = sched_res.data
        from ..database import get_period_by_id
        period = get_period_by_id(db, sched["period_id"])
    else:
        # 현 부서의 가장 최근 완료 스케줄 (현재 활성 기간 제외)
        active = get_active_period(db)
        active_period_id = active["id"] if active else None
        periods_res = db_periods(db).order("start_date", desc=True).execute()
        sched = None
        period = None
        for p in periods_res.data:
            if p["id"] == active_period_id:
                continue  # 현재 진행 중인 기간은 건너뜀
            s = (db.table("schedules").select("*")
                 .eq("period_id", p["id"])
                 .order("created_at", desc=True)
                 .limit(1).execute())
            if s.data:
                sched = s.data[0]
                period = p
                break
        if not sched:
            raise HTTPException(404,
            "이전 근무표가 존재하지 않습니다.\n"
            "이전 달 근무표 파일이 있다면 '엑셀에서 반영' 버튼을 이용해주세요."
        )

    # 현재(신규) 기간 시작일 — menstrual_used 판단 기준
    active_period = get_active_period(db)
    new_start_date = (
        date.fromisoformat(active_period["start_date"])
        if active_period and active_period.get("start_date") else None
    )

    prev_start = date.fromisoformat(period["start_date"])
    prev_month = prev_start.month
    schedule_data = sched.get("schedule_data", {})  # {nurse_uuid: {day_str: shift}}

    # 수면 규칙
    rules_res = db_rules(db).execute()
    sleep_n_monthly = rules_res.data[0].get("sleep_n_monthly", 7) if rules_res.data else 7

    nurses_res = db_nurses(db).order("sort_order").execute()
    TAIL_DAYS = 5

    results = []
    for nurse in nurses_res.data:
        nid = nurse["id"]
        shifts_raw = schedule_data.get(nid, {})
        all_shifts = {int(d): s for d, s in shifts_raw.items() if s}

        # 1. prev_tail_shifts: 마지막 5일
        tail_days_keys = sorted(all_shifts.keys())[-TAIL_DAYS:]
        prev_tail_shifts = [all_shifts[d] for d in tail_days_keys]

        # 2. prev_month_N
        prev_month_n = sum(1 for s in all_shifts.values() if s == "N")

        # 3. pending_sleep: 홀수 월 + N 기준 충족 + 수면 미사용
        sleep_used = sum(1 for s in all_shifts.values() if s == "수면")
        pending_sleep = (
            is_pair_first_month(prev_month)
            and prev_month_n >= sleep_n_monthly
            and sleep_used == 0
        )

        # 4. menstrual_used: 새 기간 시작 월에 생휴 사용 여부
        menstrual_used = False
        if new_start_date:
            for day_int, shift in all_shifts.items():
                if shift == "생휴":
                    actual = prev_start + timedelta(days=day_int - 1)
                    if actual.year == new_start_date.year and actual.month == new_start_date.month:
                        menstrual_used = True
                        break

        # 5. vacation_days: 현재값 - 사용한 휴가 수
        휴가_used = sum(1 for s in all_shifts.values() if s == "휴가")
        new_vacation_days = max(0, nurse.get("vacation_days", 0) - 휴가_used)

        update_data = {
            "prev_tail_shifts": prev_tail_shifts,
            "prev_month_n": prev_month_n,
            "pending_sleep": pending_sleep,
            "menstrual_used": menstrual_used,
            "vacation_days": new_vacation_days,
        }
        res = db_nurses(db).update(update_data).eq("id", nid).execute()
        if res.data:
            results.append(_row_to_out(res.data[0]))

    return ApplyPrevResult(
        nurses=results,
        summary=f"{len(results)}명 업데이트 완료 (전월N·수면이월·생휴·휴가잔여 자동 반영)",
    )


@router.post("/import-prev-excel", response_model=ApplyPrevResult)
def import_prev_excel(
    file: UploadFile = File(...),
    period_id: str | None = Query(None),
    _: dict = Depends(get_current_admin),
):
    """이전 달 근무표 엑셀에서 prev_tail_shifts, prev_month_N, pending_sleep, menstrual_used, vacation_days 업데이트"""
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    if root not in sys.path:
        sys.path.insert(0, root)
    from engine.models import is_pair_first_month
    from engine.excel_io import import_prev_schedule, detect_file_month, import_prev_menstrual
    from datetime import date, timedelta

    db = get_db()

    # 현재(신규) 기간: period_id가 넘어오면 해당 기간 사용, 아니면 active 기간으로 fallback
    if period_id:
        cur_period = get_period_by_id(db, period_id)
    else:
        cur_period = get_active_period(db)
    new_start_date = (
        date.fromisoformat(cur_period["start_date"])
        if cur_period and cur_period.get("start_date") else None
    )

    # 직전 기간 시작일을 DB에서 조회 (timedelta 추정 오류 방지)
    expected_prev = None
    if new_start_date:
        cur_period_id = cur_period["id"] if cur_period else None
        prev_periods = db_periods(db).order("start_date", desc=True).execute()
        for p in prev_periods.data:
            if p["id"] == cur_period_id:
                continue
            if p.get("start_date"):
                pd = date.fromisoformat(p["start_date"])
                if pd < new_start_date:
                    expected_prev = pd
                    break

    content = file.file.read()
    tmp = tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False)
    tmp.write(content)
    tmp.close()  # Windows 파일 잠금 해제 후 openpyxl 접근
    tmp_path = tmp.name

    try:
        nurses_res = db_nurses(db).order("sort_order").execute()
        nurse_names = [n["name"] for n in nurses_res.data]

        # 이전 근무표 시작일 탐지 — import_prev_schedule에 넘겨 월별 N 분류에 사용
        year, month = detect_file_month(tmp_path)
        prev_start_date = date(year, month, 1) if year and month else expected_prev

        TAIL_DAYS = 5
        tail_result, n_counts_by_month, sleep_counts, vac_days = import_prev_schedule(
            tmp_path, nurse_names, TAIL_DAYS,
            expected_start_date=expected_prev,
            start_date=prev_start_date,
        )

        # 생휴 월별 집계
        menstrual_counts = (
            import_prev_menstrual(tmp_path, nurse_names, prev_start_date)
            if prev_start_date else {}
        )

        # 수면 규칙
        rules_res = db_rules(db).execute()
        sleep_n_monthly = rules_res.data[0].get("sleep_n_monthly", 7) if rules_res.data else 7

    except ValueError as e:
        raise HTTPException(400, f"파일 검증 실패: {e}")
    except Exception as e:
        raise HTTPException(400, f"엑셀 파싱 오류: {e}")
    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass

    prev_month = prev_start_date.month if prev_start_date else 1

    results = []
    for nurse in nurses_res.data:
        name = nurse["name"]
        if name not in tail_result:
            continue  # 매칭 안 된 간호사 스킵

        by_month = n_counts_by_month.get(name, {})
        prev_month_n = sum(by_month.values())  # DB 저장용 총 N 수
        odd_month_n = by_month.get(prev_month, 0)  # 홀수 시작월 N만 (pending_sleep 판단)
        sleep_used = sleep_counts.get(name, 0)

        pending_sleep = (
            is_pair_first_month(prev_month)
            and odd_month_n >= sleep_n_monthly
            and sleep_used == 0
        )

        menstrual_used = False
        if new_start_date and name in menstrual_counts:
            menstrual_used = menstrual_counts[name].get(new_start_date.month, 0) > 0

        # vacation_days: 엑셀의 휴가잔여 열 우선, 없으면 기존값 유지
        new_vac = vac_days.get(name, nurse.get("vacation_days", 0))

        update_data = {
            "prev_tail_shifts": tail_result[name],
            "prev_month_n": prev_month_n,
            "pending_sleep": pending_sleep,
            "menstrual_used": menstrual_used,
            "vacation_days": new_vac,
        }
        res = db_nurses(db).update(update_data).eq("id", nurse["id"]).execute()
        if res.data:
            results.append(_row_to_out(res.data[0]))

    matched = len(results)
    total = len(nurses_res.data)

    if matched == 0:
        raise HTTPException(400,
            "간호사 이름이 매칭되지 않습니다.\n"
            "올바른 이전 달 근무표 파일인지 확인해주세요."
        )

    warning = ""
    if total > 0 and matched < total // 2:
        warning = f" ⚠️ {total - matched}명 미매칭 — 파일을 확인하세요"

    return ApplyPrevResult(
        nurses=results,
        summary=f"{matched}/{total}명 엑셀에서 업데이트 완료{warning}",
    )


@router.post("/import-excel", response_model=list[NurseOut])
def import_nurses_excel(file: UploadFile = File(...), _: dict = Depends(get_current_admin)):
    """근무표_규칙.xlsx → 간호사 목록 upsert"""
    # engine 경로를 sys.path에 추가
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    if root not in sys.path:
        sys.path.insert(0, root)

    from engine.excel_io import import_nurse_rules

    content = file.file.read()
    tmp = tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False)
    tmp.write(content)
    tmp.close()  # Windows 파일 잠금 해제
    tmp_path = tmp.name

    try:
        engine_nurses = import_nurse_rules(tmp_path)
    except Exception as e:
        raise HTTPException(400, f"엑셀 파싱 실패: {e}")
    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass

    db = get_db()
    # 기존 간호사 이름→UUID 맵
    existing_res = db_nurses(db).execute()
    name_to_id = {r["name"]: r["id"] for r in existing_res.data}

    results = []
    for i, nurse in enumerate(engine_nurses):
        data = {
            "department_id": settings.department_id,
            "name": nurse.name,
            "role": nurse.role,
            "grade": nurse.grade,
            "is_pregnant": nurse.is_pregnant,
            "is_male": nurse.is_male,
            "is_4day_week": nurse.is_4day_week,
            "fixed_weekly_off": nurse.fixed_weekly_off,
            "vacation_days": nurse.vacation_days,
            "prev_month_n": nurse.prev_month_N,
            "note": nurse.note,
            "sort_order": i,
        }
        if nurse.name in name_to_id:
            # 기존 간호사 업데이트 (PIN 유지)
            res = db_nurses(db).update(data).eq("id", name_to_id[nurse.name]).execute()
        else:
            data["pin_hash"] = hash_password("0000")
            res = db.table("nurses").insert(data).execute()
        results.append(_row_to_out(res.data[0]))

    return results
