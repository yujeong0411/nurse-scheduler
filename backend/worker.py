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
    from engine.solver import solve_schedule, validate_requests
    from datetime import date
    import logging

    nurses   = [Nurse.from_dict(n)   for n in nurses_data]
    requests = [Request.from_dict(r) for r in requests_data]
    rules    = Rules.from_dict(rules_data)
    start_date = date.fromisoformat(start_date_str)

    # ── 사전 진단 ──
    logging.warning(
        f"[solver] 간호사 {len(nurses)}명 | "
        f"D={rules.daily_D} E={rules.daily_E} N={rules.daily_N} 중2={rules.daily_M} | "
        f"maxN={rules.max_N_per_month} off2N={rules.off_after_2N} | "
        f"요청 {len(requests)}건 | 시작일={start_date_str}"
    )
    warnings = validate_requests(nurses, requests, rules, start_date)
    if warnings:
        logging.warning("[solver] validate_requests 경고:\n" + "\n".join(f"  - {w}" for w in warnings))

    schedule = solve_schedule(nurses, requests, rules, start_date, timeout_seconds)

    if not schedule.schedule_data:
        raise RuntimeError(
            "INFEASIBLE — 해를 찾을 수 없습니다.\n"
            + (("사전 경고:\n" + "\n".join(f"  - {w}" for w in warnings)) if warnings else "사전 경고 없음 (규칙/인원 충돌 가능성)")
        )

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

        nurses_data   = _convert_nurses(nurses_res.data)
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

        # assignment_log 생성 (우선순위 신청이 있는 날짜-코드 단위)
        _save_assignment_log(db, period_id, requests_data, result)

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


def _convert_nurses(nurses_data: list[dict]) -> list[dict]:
    """DB nurses → engine Nurse.from_dict 형식
    DB는 snake_case 소문자(prev_month_n), engine은 대문자(prev_month_N) 사용"""
    result = []
    for n in nurses_data:
        converted = dict(n)
        converted["prev_month_N"] = n.get("prev_month_n", 0)
        result.append(converted)
    return result


def _convert_requests(raw_requests: list[dict], nurses: list[dict]) -> list[dict]:
    """DB requests → engine Request.from_dict 형식 (nurse_id UUID 그대로 유지)

    score는 DB 저장값 대신 현재 신청 데이터에서 직접 재계산.
    엑셀 임포트 등으로 score 컬럼이 100 고정이어도 실제 신청 수 기반으로 올바른 값 사용.
    """
    _SKIP = {"병가", "법휴", "필수"}
    nurse_ids = {n["id"] for n in nurses}

    # 간호사별 점수 재계산: 100 - (A신청×1 + B신청×3), 제외 코드 제외
    deductions: dict[str, int] = {}
    for r in raw_requests:
        if r["nurse_id"] not in nurse_ids:
            continue
        if r.get("code") in _SKIP:
            continue
        cond = r.get("condition") or "B"
        nid = r["nurse_id"]
        deductions[nid] = deductions.get(nid, 0) + (1 if cond == "A" else 3)

    computed_scores: dict[str, int] = {nid: 100 - d for nid, d in deductions.items()}

    result = []
    for r in raw_requests:
        if r["nurse_id"] not in nurse_ids:
            continue
        result.append({
            "nurse_id": r["nurse_id"],
            "day": r["day"],
            "code": r["code"],
            "is_or": r.get("is_or", False),
            "condition": r.get("condition") or "B",
            "score": computed_scores.get(r["nurse_id"], 100),  # 재계산된 점수 사용
        })
    return result


def _parse_holidays(val) -> list[int]:
    """DB에서 public_holidays가 '[]' 같은 문자열로 올 때 파싱"""
    import json as _json
    if isinstance(val, str):
        try:
            val = _json.loads(val)
        except Exception:
            return []
    if not val:
        return []
    return [int(x) for x in val]


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
        "public_holidays":      _parse_holidays(raw.get("public_holidays", [])),
    }


def _save_assignment_log(db, period_id: str, requests_data: list[dict], result: dict) -> None:
    """solver 결과와 신청 목록을 비교해 assignment_log 저장

    (day, code) 단위로 신청자를 우선순위 정렬 후
    solver 배정 결과와 대조해 is_assigned, rank, is_random 기록
    """
    import random as _random
    from collections import defaultdict

    # nurse_id+day → 해당 날 신청한 모든 코드 목록 (requested_codes 표시용)
    nurse_day_codes: dict[tuple, list] = defaultdict(list)
    for r in requests_data:
        if r["code"] not in {"병가", "법휴", "필수"}:
            nurse_day_codes[(r["nurse_id"], r["day"])].append(r["code"])

    # (day, code) → [request_dict, ...]
    groups: dict[tuple, list] = defaultdict(list)
    for r in requests_data:
        # 우선순위 적용 대상: 병가/법휴/필수 제외
        if r["code"] in {"병가", "법휴", "필수"}:
            continue
        groups[(r["day"], r["code"])].append(r)

    # 신청자가 2명 이상인 그룹만 로그 생성 (경쟁 없으면 불필요)
    log_rows = []
    for (day, code), applicants in groups.items():
        if len(applicants) < 2:
            continue

        # 우선순위 정렬: A > B → score 높은 순 → 동점 랜덤
        max_score = max(a["score"] for a in applicants)
        for a in applicants:
            a["_rand"] = _random.random()

        sorted_applicants = sorted(
            applicants,
            key=lambda a: (
                0 if a["condition"] == "A" else 1,  # A 먼저
                -a["score"],                         # 점수 높은 순
                a["_rand"],                          # 동점 랜덤
            )
        )

        # 동점(같은 condition, 같은 score) 여부 확인
        def _is_random_used(lst):
            for i in range(len(lst) - 1):
                a, b = lst[i], lst[i + 1]
                if a["condition"] == b["condition"] and a["score"] == b["score"]:
                    return True
            return False

        is_random = _is_random_used(sorted_applicants)

        # solver 배정 결과에서 이 (day, code) 배정 여부 확인
        _ALL_OFF = {'주', 'OFF', '법휴', '수면', '생휴', '휴가', '병가', '특휴', '공가', '경가', '보수', 'POFF', '필수', '번표'}
        code_is_off = code in _ALL_OFF
        day_str = str(day)
        for rank, applicant in enumerate(sorted_applicants, start=1):
            nid = applicant["nurse_id"]
            assigned_shift = result.get(nid, {}).get(day_str, "")
            if code_is_off:
                is_assigned = assigned_shift in _ALL_OFF
            else:
                is_assigned = (assigned_shift == code)
            all_codes = nurse_day_codes.get((nid, day), [code])
            requested_codes = "/".join(dict.fromkeys(all_codes))  # 중복 제거, 순서 유지
            log_rows.append({
                "period_id": period_id,
                "day": day,
                "code": code,
                "requested_codes": requested_codes,
                "nurse_id": nid,
                "condition": applicant["condition"],
                "score": applicant["score"],
                "rank": rank,
                "is_random": is_random,
                "is_assigned": is_assigned,
            })

    if not log_rows:
        return

    # 기존 로그 삭제 후 재삽입 (재생성 시 중복 방지)
    try:
        db.table("assignment_log").delete().eq("period_id", period_id).execute()
        db.table("assignment_log").insert(log_rows).execute()
    except Exception:
        pass  # 로그 실패는 근무표 생성에 영향 없음
