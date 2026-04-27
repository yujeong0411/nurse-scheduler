"""실제 DB 데이터로 솔버를 직접 실행하는 진단 스크립트

사용법:
  uv run python test_solver_direct.py [start_date]
  예) uv run python test_solver_direct.py 2026-02-01

start_date 미지정 시 가장 최근 period 사용.
"""
import sys
import os

# engine/ 경로 추가
ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from supabase import create_client
from engine.models import Nurse, Request, Rules
from engine.solver import solve_schedule
from datetime import date
import json

# ── .env에서 직접 읽기 ──────────────────────────────────────────
def _load_env():
    env_path = os.path.join(ROOT, "backend", ".env")
    env = {}
    with open(env_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and "=" in line and not line.startswith("#"):
                k, _, v = line.partition("=")
                env[k.strip()] = v.strip()
    return env

env = _load_env()
SUPABASE_URL = env["SUPABASE_URL"]
SUPABASE_KEY = env["SUPABASE_SERVICE_KEY"]
DEPARTMENT_ID = env["DEPARTMENT_ID"]

db = create_client(SUPABASE_URL, SUPABASE_KEY)

# ── period 선택 ──────────────────────────────────────────────────
if len(sys.argv) > 1:
    start_date_str = sys.argv[1]
    period_res = (
        db.table("periods")
        .select("*")
        .eq("department_id", DEPARTMENT_ID)
        .eq("start_date", start_date_str)
        .execute()
    )
    if not period_res.data:
        print(f"[ERROR] start_date={start_date_str} period 없음")
        sys.exit(1)
    period = period_res.data[0]
else:
    period_res = (
        db.table("periods")
        .select("*")
        .eq("department_id", DEPARTMENT_ID)
        .execute()
    )
    if not period_res.data:
        print("[ERROR] period 없음")
        sys.exit(1)
    period = max(period_res.data, key=lambda p: p["start_date"])

period_id = period["id"]
start_date_str = period["start_date"]
print(f"[INFO] period_id={period_id}  start_date={start_date_str}")

# ── 데이터 로드 ──────────────────────────────────────────────────
nurses_res = (
    db.table("nurses")
    .select("*")
    .eq("department_id", DEPARTMENT_ID)
    .order("sort_order")
    .execute()
)
req_res = db.table("requests").select("*").eq("period_id", period_id).execute()
rules_res = db.table("rules").select("*").eq("department_id", DEPARTMENT_ID).execute()

print(f"[INFO] 간호사 {len(nurses_res.data)}명 | 신청 {len(req_res.data)}건")

# ── worker.py 변환 함수 복사 ──────────────────────────────────────
def _convert_nurses(nurses_data):
    result = []
    for n in nurses_data:
        converted = dict(n)
        converted["prev_month_N"] = n.get("prev_month_n", 0)
        result.append(converted)
    return result

def _parse_holidays(val):
    import json as _json
    if isinstance(val, str):
        try:
            val = _json.loads(val)
        except Exception:
            return []
    if not val:
        return []
    return [int(x) for x in val]

def _convert_rules(raw):
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

def _convert_requests(raw_requests, nurses):
    _SKIP = {"병가", "법휴", "필수"}
    nurse_ids = {n["id"] for n in nurses}
    deductions = {}
    for r in raw_requests:
        if r["nurse_id"] not in nurse_ids:
            continue
        if r.get("code") in _SKIP:
            continue
        cond = r.get("condition") or "B"
        nid = r["nurse_id"]
        deductions[nid] = deductions.get(nid, 0) + (1 if cond == "A" else 3)
    computed_scores = {nid: 100 - d for nid, d in deductions.items()}
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
            "score": computed_scores.get(r["nurse_id"], 100),
        })
    return result

# ── 변환 ──────────────────────────────────────────────────────────
nurses_data   = _convert_nurses(nurses_res.data)
requests_data = _convert_requests(req_res.data, nurses_data)
rules_raw     = rules_res.data[0] if rules_res.data else {}
rules_data    = _convert_rules(rules_raw)

nurses   = [Nurse.from_dict(n)   for n in nurses_data]
requests = [Request.from_dict(r) for r in requests_data]
rules    = Rules.from_dict(rules_data)
start_date = date.fromisoformat(start_date_str)

# ── 간호사 요약 출력 ──────────────────────────────────────────────
fourday_count  = sum(1 for n in nurses if n.is_4day_week)
regular_count  = len(nurses) - fourday_count
female_count   = sum(1 for n in nurses if not n.is_male)
pregnant_count = sum(1 for n in nurses if n.is_pregnant)
fwo_count      = sum(1 for n in nurses if n.fixed_weekly_off is not None)
print(f"[INFO] 일반={regular_count} 주4일={fourday_count} | 여성={female_count} 임산부={pregnant_count} | FWO보유={fwo_count}")
print(f"[INFO] rules: D={rules.daily_D} E={rules.daily_E} N={rules.daily_N} 중2={rules.daily_M} | 공휴일={rules.public_holidays}")

# NN 꼬리 보유 간호사 출력
nn_tail_nurses = [n.name for n in nurses if len(n.prev_tail_shifts or []) >= 2 and n.prev_tail_shifts[-2] == "N" and n.prev_tail_shifts[-1] == "N"]
if nn_tail_nurses:
    print(f"[INFO] NN 꼬리 간호사: {nn_tail_nurses}")

timeout_sec = rules_raw.get("solver_timeout", 300)
print(f"\n[RUN] 솔버 실행 (timeout={timeout_sec}s)...")
print("=" * 60)

schedule = solve_schedule(nurses, requests, rules, start_date, timeout_seconds=timeout_sec)

print("=" * 60)
if schedule.schedule_data:
    total_assigned = sum(len(v) for v in schedule.schedule_data.values())
    print(f"\n[RESULT] FEASIBLE ✓  (배정 셀 수: {total_assigned})")
else:
    print(f"\n[RESULT] INFEASIBLE / TIMEOUT ✗")
