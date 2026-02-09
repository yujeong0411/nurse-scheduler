"""스케줄링 엔진 - Google OR-Tools CP-SAT Solver
응급실 간호사 근무표 생성

Hard Constraints (23개):
 H1.  하루 1배정
 H2.  일일 인원 (D 7, E 8, N 7)
 H3.  역순 금지 (D→중간→E→N)
 H4.  최대 연속 근무 (5일)
 H5.  최대 연속 N (3개)
 H6.  N 2연속 후 휴무 2개
 H7.  월 N 제한 (6개)
 H8.  확정 요청 (주, 법휴, 휴, 연차, 특휴, 공, 경, 수면)
 H9.  제외 요청 (D 제외, E 제외, N 제외)
 H10. 고정 주휴 (매주 고정 요일)
 H11. 주당 휴무 2개 이상
 H12. 책임 1명 이상 (매 근무)
 H13. 책임+서브차지 2명 이상 (매 근무)
 H14. 역할 누적 제한 (ROLE_TIERS)
 H15. 책임만 1명 이하 (매 근무)
 H16. 주4일제 (주당 OFF 3개)
 H17. 임산부 (4연속 근무 제한)
 H18. 월 N 제한 (6개) — H7과 동일
 H19. 법정공휴일 휴무 = 법휴 (후처리)
 H20. 연차 잔여일 체크 (validator에서 처리)
 H21. 수면 조건 (후처리)
 H22. 생리휴무 (후처리)
 H23. 전월 미사용 수면 (후처리)

Soft Constraints:
 S1. 희망 요청 반영 (+10)
 S2. D/E/N 횟수 공정 (-5)
 S3. N 균등 배분 (-8)
 S4. 주말 균등 배분 (-8)
 S5. 일반 3명 이하 권고 (-3)

후처리:
 P1. OFF → 주/법휴/생/수면/POFF 라벨링
"""
import calendar
from ortools.sat.python import cp_model
from engine.models import (
    Nurse, Request, Rules, Schedule,
    WORK_SHIFTS, OFF_TYPES, SHIFT_ORDER, ROLE_TIERS,
    get_sleep_partner_month,
)


# ══════════════════════════════════════════
# 솔버 내 근무 타입 인덱스
# ══════════════════════════════════════════

# 근무 (7종)
_D, _D9, _D1, _M1, _M2, _E, _N = 0, 1, 2, 3, 4, 5, 6

# 휴무 (솔버 내 통합 OFF)
_OFF = 7

NUM_TYPES = 8

# 인덱스 ↔ 이름
IDX_TO_NAME = {
    _D: "D", _D9: "D9", _D1: "D1", _M1: "중1", _M2: "중2",
    _E: "E", _N: "N", _OFF: "OFF",
}
NAME_TO_IDX = {v: k for k, v in IDX_TO_NAME.items()}

# 근무 패밀리 (인원 집계용)
D_FAMILY = [_D, _D9, _D1]          # 주간 계열
E_FAMILY = [_M1, _M2, _E]          # 오후/저녁 계열
N_FAMILY = [_N]                     # 야간
WORK_INDICES = [_D, _D9, _D1, _M1, _M2, _E, _N]

# 근무 순서 레벨 (역순 금지용)
SHIFT_LEVEL = {
    _D: 1,
    _D9: 2, _D1: 2, _M1: 2, _M2: 2,
    _E: 3,
    _N: 4,
}

# 역순 금지 페어 (미리 계산)
FORBIDDEN_PAIRS = [
    (si, sj) for si in WORK_INDICES for sj in WORK_INDICES
    if SHIFT_LEVEL[si] > SHIFT_LEVEL[sj]
]


def solve_schedule(
    nurses: list[Nurse],
    requests: list[Request],
    rules: Rules,
    year: int,
    month: int,
    timeout_seconds: int = 60,
) -> Schedule:
    """OR-Tools CP-SAT으로 최적 근무표 생성"""

    num_days = calendar.monthrange(year, month)[1]
    num_nurses = len(nurses)

    model = cp_model.CpModel()

    # ──────────────────────────────────────────
    # 변수 정의: shifts[(ni, di, si)] = BoolVar
    # ni: 간호사 인덱스 (0~37)
    # di: 날짜 인덱스 (0~27, 0-based)
    # si: 근무 타입 (0~7)
    # ──────────────────────────────────────────
    shifts = {}
    for ni in range(num_nurses):
        for di in range(num_days):
            for si in range(NUM_TYPES):
                shifts[(ni, di, si)] = model.new_bool_var(f"s_n{ni}_d{di}_s{si}")

    # 인덱스 맵
    nurse_idx = {nurse.id: i for i, nurse in enumerate(nurses)}

    # 요청 맵: (nurse_id, day) → Request
    req_map = {}
    for r in requests:
        req_map[(r.nurse_id, r.day)] = r

    # 헬퍼 함수
    def weekday_of(di):
        """di(0-based) → 요일 (0=월...6=일)"""
        return calendar.weekday(year, month, di + 1)

    num_weeks = (num_days + 6) // 7

    # ══════════════════════════════════════════
    # HARD CONSTRAINTS
    # ══════════════════════════════════════════

    # ── H1. 하루에 정확히 1개 배정 ──
    for ni in range(num_nurses):
        for di in range(num_days):
            model.add(
                sum(shifts[(ni, di, si)] for si in range(NUM_TYPES)) == 1
            )

    # ── H2. 일일 인원 ──
    for di in range(num_days):
        # D 계열 (D + D9 + D1) >= daily_D
        model.add(
            sum(shifts[(ni, di, si)]
                for ni in range(num_nurses) for si in D_FAMILY)
            >= rules.daily_D
        )
        # E 계열 (중1 + 중2 + E) >= daily_E
        model.add(
            sum(shifts[(ni, di, si)]
                for ni in range(num_nurses) for si in E_FAMILY)
            >= rules.daily_E
        )
        # N >= daily_N
        model.add(
            sum(shifts[(ni, di, _N)] for ni in range(num_nurses))
            >= rules.daily_N
        )

    # ── H3. 역순 금지 ──
    # D(1)→중간(2)→E(3)→N(4) 순서만 허용
    # 높은 레벨 → 낮은 레벨 연속 금지
    if rules.ban_reverse_order:
        for ni in range(num_nurses):
            for di in range(num_days - 1):
                for si, sj in FORBIDDEN_PAIRS:
                    model.add(
                        shifts[(ni, di, si)] + shifts[(ni, di + 1, sj)] <= 1
                    )

    # ── H4. 최대 연속 근무 (5일) ──
    max_cw = rules.max_consecutive_work
    for ni in range(num_nurses):
        for di in range(num_days - max_cw):
            # (max_cw+1)일 구간에서 OFF 최소 1개
            model.add(
                sum(shifts[(ni, di + dd, _OFF)]
                    for dd in range(max_cw + 1)) >= 1
            )

    # ── H5. 최대 연속 N (3개) ──
    max_cn = rules.max_consecutive_N
    for ni in range(num_nurses):
        for di in range(num_days - max_cn):
            model.add(
                sum(shifts[(ni, di + dd, _N)]
                    for dd in range(max_cn + 1)) <= max_cn
            )

    # ── H6. N 2연속 후 휴무 2개 ──
    # N(di) + N(di+1) = 2이면 → di+2, di+3 반드시 OFF
    off_after = rules.off_after_2N
    for ni in range(num_nurses):
        for di in range(num_days - 1):
            for k in range(off_after):
                if di + 2 + k < num_days:
                    # N+N=2 → 2-1=1 → OFF(di+2+k) >= 1
                    model.add(
                        shifts[(ni, di, _N)] + shifts[(ni, di + 1, _N)] - 1
                        <= shifts[(ni, di + 2 + k, _OFF)]
                    )

    # ── H7. 월 N 제한 (6개) ──
    for ni in range(num_nurses):
        model.add(
            sum(shifts[(ni, di, _N)] for di in range(num_days))
            <= rules.max_N_per_month
        )

    # ── H8. 확정 요청 ──
    # 주, 법휴, 휴, 연차, 특휴, 공, 경, 수면 → 해당 날짜 OFF 강제
    for r in requests:
        if not r.is_hard:
            continue
        if r.nurse_id not in nurse_idx:
            continue
        ni = nurse_idx[r.nurse_id]
        di = r.day - 1
        if 0 <= di < num_days:
            model.add(shifts[(ni, di, _OFF)] == 1)

    # ── H9. 제외 요청 ──
    # "D 제외" → 그 날 D계열 전부 금지
    for r in requests:
        if not r.is_exclude:
            continue
        if r.nurse_id not in nurse_idx:
            continue
        ni = nurse_idx[r.nurse_id]
        di = r.day - 1
        if di < 0 or di >= num_days:
            continue
        excluded = r.excluded_shift
        if excluded == "D":
            for si in D_FAMILY:
                model.add(shifts[(ni, di, si)] == 0)
        elif excluded == "E":
            for si in E_FAMILY:
                model.add(shifts[(ni, di, si)] == 0)
        elif excluded == "N":
            model.add(shifts[(ni, di, _N)] == 0)

    # ── H10. 고정 주휴 ──
    # 매주 고정 요일에 OFF 강제
    for ni, nurse in enumerate(nurses):
        if nurse.fixed_weekly_off is not None:
            for di in range(num_days):
                if weekday_of(di) == nurse.fixed_weekly_off:
                    model.add(shifts[(ni, di, _OFF)] == 1)

    # ── H11. 주당 휴무 최소 2개 ──
    for ni in range(num_nurses):
        for wk in range(num_weeks):
            start = wk * 7
            end = min(start + 7, num_days)
            days_in_week = end - start
            # 마지막 불완전 주: 비례 적용
            if days_in_week < 7:
                min_off = max(1, rules.min_weekly_off * days_in_week // 7)
            else:
                min_off = rules.min_weekly_off
            model.add(
                sum(shifts[(ni, di, _OFF)] for di in range(start, end))
                >= min_off
            )

    # ── H12. 책임 1명 이상 (매 근무) ──
    chiefs = [ni for ni, n in enumerate(nurses) if n.grade == "책임"]
    if chiefs and rules.min_chief_per_shift > 0:
        for di in range(num_days):
            # D 계열
            model.add(
                sum(shifts[(ni, di, si)]
                    for ni in chiefs for si in D_FAMILY)
                >= rules.min_chief_per_shift
            )
            # E 계열
            model.add(
                sum(shifts[(ni, di, si)]
                    for ni in chiefs for si in E_FAMILY)
                >= rules.min_chief_per_shift
            )
            # N
            model.add(
                sum(shifts[(ni, di, _N)] for ni in chiefs)
                >= rules.min_chief_per_shift
            )

    # ── H13. 책임+서브차지 2명 이상 (매 근무) ──
    seniors = [ni for ni, n in enumerate(nurses)
               if n.grade in ("책임", "서브차지")]
    if seniors and rules.min_senior_per_shift > 0:
        for di in range(num_days):
            model.add(
                sum(shifts[(ni, di, si)]
                    for ni in seniors for si in D_FAMILY)
                >= rules.min_senior_per_shift
            )
            model.add(
                sum(shifts[(ni, di, si)]
                    for ni in seniors for si in E_FAMILY)
                >= rules.min_senior_per_shift
            )
            model.add(
                sum(shifts[(ni, di, _N)] for ni in seniors)
                >= rules.min_senior_per_shift
            )

    # ── H14. 역할 누적 제한 ──
    # ROLE_TIERS: 각 티어별 역할 집합의 동시 근무 최대 인원
    for tier_roles, max_d, max_e, max_n in ROLE_TIERS:
        tier_nurses = [ni for ni, n in enumerate(nurses)
                       if n.role in tier_roles]
        if not tier_nurses:
            continue
        for di in range(num_days):
            model.add(
                sum(shifts[(ni, di, si)]
                    for ni in tier_nurses for si in D_FAMILY)
                <= max_d
            )
            model.add(
                sum(shifts[(ni, di, si)]
                    for ni in tier_nurses for si in E_FAMILY)
                <= max_e
            )
            model.add(
                sum(shifts[(ni, di, _N)] for ni in tier_nurses)
                <= max_n
            )

    # ── H15. 책임만 1명 이하 (매 근무) ──
    chief_only = [ni for ni, n in enumerate(nurses)
                  if n.role == "책임만"]
    if chief_only:
        for di in range(num_days):
            model.add(
                sum(shifts[(ni, di, si)]
                    for ni in chief_only for si in D_FAMILY)
                <= 1
            )
            model.add(
                sum(shifts[(ni, di, si)]
                    for ni in chief_only for si in E_FAMILY)
                <= 1
            )
            model.add(
                sum(shifts[(ni, di, _N)] for ni in chief_only)
                <= 1
            )

    # ── H16. 주4일제 → 주당 OFF 3개 (주7일 - 근무4일) ──
    for ni, nurse in enumerate(nurses):
        if not nurse.is_4day_week:
            continue
        for wk in range(num_weeks):
            start = wk * 7
            end = min(start + 7, num_days)
            days_in_week = end - start
            if days_in_week < 7:
                min_off = max(1, 3 * days_in_week // 7)
            else:
                min_off = 3
            model.add(
                sum(shifts[(ni, di, _OFF)] for di in range(start, end))
                >= min_off
            )

    # ── H17. 임산부 → 최대 연속 근무 4일 ──
    for ni, nurse in enumerate(nurses):
        if not nurse.is_pregnant:
            continue
        interval = rules.pregnant_poff_interval  # 4
        for di in range(num_days - interval):
            model.add(
                sum(shifts[(ni, di + dd, _OFF)]
                    for dd in range(interval + 1)) >= 1
            )

    # ══════════════════════════════════════════
    # SOFT CONSTRAINTS (목적함수)
    # ══════════════════════════════════════════
    obj = []

    # ── S1. 희망 요청 반영 (+10) ──
    for r in requests:
        if r.is_hard or r.is_exclude:
            continue
        if r.nurse_id not in nurse_idx:
            continue
        ni = nurse_idx[r.nurse_id]
        di = r.day - 1
        if di < 0 or di >= num_days:
            continue

        if r.code == "OFF":
            obj.append(10 * shifts[(ni, di, _OFF)])
        elif r.code in NAME_TO_IDX:
            si = NAME_TO_IDX[r.code]
            obj.append(10 * shifts[(ni, di, si)])

    # ── S2. D/E/N 횟수 공정성 (-5) ──
    # 각 간호사별 D계열/E계열/N 횟수 편차 최소화
    shift_counts = {}
    for ni in range(num_nurses):
        for family, label in [(D_FAMILY, "D"), (E_FAMILY, "E"), ([_N], "N")]:
            c = model.new_int_var(0, num_days, f"cnt_n{ni}_{label}")
            model.add(c == sum(
                shifts[(ni, di, si)]
                for di in range(num_days) for si in family
            ))
            shift_counts[(ni, label)] = c

    for label in ["D", "E", "N"]:
        all_counts = [shift_counts[(ni, label)] for ni in range(num_nurses)]
        if len(all_counts) >= 2:
            mx = model.new_int_var(0, num_days, f"max_{label}")
            mn = model.new_int_var(0, num_days, f"min_{label}")
            model.add_max_equality(mx, all_counts)
            model.add_min_equality(mn, all_counts)
            diff = model.new_int_var(0, num_days, f"diff_{label}")
            model.add(diff == mx - mn)
            obj.append(-5 * diff)

    # ── S3. N 균등 배분 (-8) ──
    n_counts = [shift_counts[(ni, "N")] for ni in range(num_nurses)]
    if len(n_counts) >= 2:
        mx = model.new_int_var(0, num_days, "max_N_eq")
        mn = model.new_int_var(0, num_days, "min_N_eq")
        model.add_max_equality(mx, n_counts)
        model.add_min_equality(mn, n_counts)
        diff = model.new_int_var(0, num_days, "N_eq_diff")
        model.add(diff == mx - mn)
        obj.append(-8 * diff)

    # ── S4. 주말 균등 배분 (-8) ──
    weekend_indices = [di for di in range(num_days) if weekday_of(di) >= 5]
    if weekend_indices and num_nurses >= 2:
        max_wk_work = len(weekend_indices) * len(WORK_INDICES)
        wk_counts = []
        for ni in range(num_nurses):
            c = model.new_int_var(0, max_wk_work, f"wk_n{ni}")
            model.add(c == sum(
                shifts[(ni, di, si)]
                for di in weekend_indices for si in WORK_INDICES
            ))
            wk_counts.append(c)

        mx = model.new_int_var(0, max_wk_work, "max_wk")
        mn = model.new_int_var(0, max_wk_work, "min_wk")
        model.add_max_equality(mx, wk_counts)
        model.add_min_equality(mn, wk_counts)
        diff = model.new_int_var(0, max_wk_work, "wk_diff")
        model.add(diff == mx - mn)
        obj.append(-8 * diff)

    # ── S5. 일반 3명 이하 권고 (-3) ──
    juniors = [ni for ni, n in enumerate(nurses) if n.grade == ""]
    if juniors:
        for di in range(num_days):
            for family, tag in [(D_FAMILY, "D"), (E_FAMILY, "E"), ([_N], "N")]:
                over = model.new_int_var(
                    0, len(juniors), f"jr_d{di}_{tag}")
                jr_cnt = sum(
                    shifts[(ni, di, si)]
                    for ni in juniors for si in family
                )
                model.add(over >= jr_cnt - rules.max_junior_per_shift)
                obj.append(-3 * over)

    # ── 목적함수 설정 ──
    if obj:
        model.maximize(sum(obj))

    # ══════════════════════════════════════════
    # 솔버 실행
    # ══════════════════════════════════════════
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = timeout_seconds
    solver.parameters.num_workers = 4

    status = solver.solve(model)

    # ══════════════════════════════════════════
    # 결과 추출
    # ══════════════════════════════════════════
    schedule = Schedule(
        year=year, month=month,
        nurses=nurses, rules=rules, requests=requests,
    )

    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        for ni, nurse in enumerate(nurses):
            for di in range(num_days):
                for si in range(NUM_TYPES):
                    if solver.value(shifts[(ni, di, si)]):
                        schedule.set_shift(nurse.id, di + 1, IDX_TO_NAME[si])
                        break

        # 후처리: OFF 라벨링
        _post_process(schedule, nurses, requests, rules, year, month)

    return schedule


# ══════════════════════════════════════════
# 후처리: OFF → 구체적 휴무 라벨링
# ══════════════════════════════════════════

def _post_process(
    schedule: Schedule,
    nurses: list[Nurse],
    requests: list[Request],
    rules: Rules,
    year: int,
    month: int,
):
    """솔버가 배정한 OFF를 구체적 휴무 코드로 라벨링

    라벨링 순서 (우선순위):
    1. 확정 요청 (주, 법휴, 휴, 연차, 특휴, 공, 경, 수면)
    2. 고정 주휴
    3. 법정공휴일 → 법휴
    4. 생리휴무 (남자 제외 월 1개)
    5. 수면 (조건 충족 시)
    6. 임산부 POFF
    7. 나머지 → OFF 유지
    """
    num_days = schedule.num_days

    # 요청 맵: nurse_id → {day: Request}
    req_by_nurse = {}
    for r in requests:
        req_by_nurse.setdefault(r.nurse_id, {})[r.day] = r

    for nurse in nurses:
        nid = nurse.id
        nurse_reqs = req_by_nurse.get(nid, {})

        # ── P1. 확정 요청 라벨링 ──
        for day in range(1, num_days + 1):
            if schedule.get_shift(nid, day) != "OFF":
                continue
            r = nurse_reqs.get(day)
            if r and r.is_hard:
                schedule.set_shift(nid, day, r.code)

        # ── P2. 고정 주휴 라벨링 ──
        if nurse.fixed_weekly_off is not None:
            for day in range(1, num_days + 1):
                if schedule.weekday_index(day) == nurse.fixed_weekly_off:
                    s = schedule.get_shift(nid, day)
                    if s == "OFF":
                        schedule.set_shift(nid, day, "주")

        # ── P3. 법정공휴일 → 법휴 ──
        # 공휴일에 OFF인데 "주"가 아니면 → "법휴"
        for day in rules.public_holidays:
            if day < 1 or day > num_days:
                continue
            s = schedule.get_shift(nid, day)
            if s == "OFF":
                schedule.set_shift(nid, day, "법휴")
            # "주"는 유지 (주휴 우선)

        # ── P4. 생리휴무 (남자 제외, 월 1개) ──
        if not nurse.is_male and rules.menstrual_leave:
            for day in range(1, num_days + 1):
                if schedule.get_shift(nid, day) == "OFF":
                    schedule.set_shift(nid, day, "생")
                    break  # 월 1개만

        # ── P5. 수면 라벨링 ──
        _label_sleep(schedule, nurse, rules, year, month)

        # ── P6. 임산부 POFF 라벨링 ──
        if nurse.is_pregnant:
            _label_poff(schedule, nurse, rules)


def _label_sleep(
    schedule: Schedule,
    nurse: Nurse,
    rules: Rules,
    year: int,
    month: int,
):
    """수면휴무 라벨링

    발생 조건:
    - 당월 N >= 7
    - 짝수월: 전월+당월 N 합산 >= 11 (1-2월, 3-4월, 5-6월 ... 페어)
    - 전월 미사용 수면(pending_sleep) 이월

    조건 충족 다음날부터 수면 사용 가능
    """
    nid = nurse.id
    num_days = schedule.num_days

    needs_sleep = False
    sleep_available_from = 1  # 수면 사용 가능 시작일

    # 전월 미사용 수면 → 1일부터 사용 가능
    if nurse.pending_sleep:
        needs_sleep = True
        sleep_available_from = 1

    # 2개월 페어 체크 (짝수월만: 2월, 4월, 6월 ...)
    partner = get_sleep_partner_month(month)

    # 당월 N 누적으로 발생하는 수면
    n_cumulative = 0
    for day in range(1, num_days + 1):
        if schedule.get_shift(nid, day) == "N":
            n_cumulative += 1

        # 당월 N >= sleep_N_monthly (7)
        if n_cumulative >= rules.sleep_N_monthly and not needs_sleep:
            needs_sleep = True
            sleep_available_from = day + 1  # 조건 충족 다음날

        # 짝수월: 2개월 합산 체크 (1-2, 3-4, 5-6 ...)
        if partner is not None and not needs_sleep:
            total_n = nurse.prev_month_N + n_cumulative
            if total_n >= rules.sleep_N_bimonthly:
                needs_sleep = True
                sleep_available_from = day + 1

    # 수면 배정
    if needs_sleep:
        for day in range(sleep_available_from, num_days + 1):
            if schedule.get_shift(nid, day) == "OFF":
                schedule.set_shift(nid, day, "수면")
                break  # 1개만 (2조건 동시 충족 시에도 1개)


def _label_poff(schedule: Schedule, nurse: Nurse, rules: Rules):
    """임산부 POFF 라벨링

    4연속 근무 후 첫 OFF를 POFF로 라벨링
    """
    nid = nurse.id
    num_days = schedule.num_days
    interval = rules.pregnant_poff_interval  # 4

    consecutive_work = 0
    for day in range(1, num_days + 1):
        s = schedule.get_shift(nid, day)
        if s in WORK_SHIFTS:
            consecutive_work += 1
        elif consecutive_work >= interval and s == "OFF":
            schedule.set_shift(nid, day, "POFF")
            consecutive_work = 0
        else:
            consecutive_work = 0
