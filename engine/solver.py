"""스케줄링 엔진 - Google OR-Tools CP-SAT Solver
응급실 간호사 근무표 생성

Hard Constraints (17개):
 H1.  하루 1배정 (D/E/N/OFF/LEAVE 중 1개)
 H2.  일일 인원 (D 7, E 8, N 7)
 H3.  역순 금지 (D→중간→E→N)
 H4.  최대 연속 근무 (5일) — OFF+LEAVE 모두 비근무로 인정
 H5.  최대 연속 N (3개)
 H6.  N 2연속 후 휴무 2개 — OFF+LEAVE 모두 비근무로 인정
 H7.  월 N 제한 (6개)
 H8.  확정 요청: 주/OFF → _OFF, 생휴/수면/법휴/휴가/공가/경가 → _LEAVE
 H9.  제외 요청 (D 제외, E 제외, N 제외)
 H10. 고정 주휴 (매주 고정 요일 → _OFF)
 H11. 주당 정규 휴무 (OFF == 2, 주4일제 == 3) — LEAVE는 별도 추가
 H12. 책임 1명 이상 (매 근무)
 H13. 책임+서브차지 N명 이상 (매 근무)
 H14. 역할 누적 제한 (ROLE_TIERS)
 H15. 책임만 1명 이하 (매 근무)
 H16. (H11에 통합)
 H17. 임산부 (4연속 근무 제한) — OFF+LEAVE 모두 비근무로 인정

LEAVE 자동 배정:
 L1. 여성 간호사 → LEAVE >= 1 (생휴용)
 L2. 전월 미사용 수면 → LEAVE >= 1 추가 (수면용)

Soft Constraints:
 S1. 희망 요청 반영 (+10)
 S2. D/E/N 횟수 공정 (-5)
 S3. N 균등 배분 (-8)
 S4. 주말 균등 배분 (-8)
 S5. 일반 3명 이하 권고 (-3)

후처리:
 P1. OFF → 주 (고정 주휴일) / 나머지 OFF 유지
 P2. LEAVE → 확정 요청 코드 / 생휴 / 수면 / POFF / 법휴
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

# 근무
_D, _E, _N = 0, 1, 2
# _D, _D9, _D1, _M1, _M2, _E, _N = 0, 1, 2, 3, 4, 5, 6

# 정규 휴무 (주 + OFF)
_OFF = 3

# 특수 휴무 (생휴, 수면, 법휴, 휴가, 공가, 경가, POFF)
_LEAVE = 4

NUM_TYPES = 5      # D, E, N, OFF, LEAVE

# 인덱스 ↔ 이름
IDX_TO_NAME = {
    _D: "D",
    # _D9: "D9", _D1: "D1", _M1: "중1", _M2: "중2",
    _E: "E", _N: "N", _OFF: "OFF", _LEAVE: "LEAVE",
}
NAME_TO_IDX = {v: k for k, v in IDX_TO_NAME.items()}

# 특수 휴무로 분류되는 요청 코드 (솔버에서 _LEAVE로 매핑)
LEAVE_CODES = {"생휴", "수면", "법휴", "휴가", "특휴", "공가", "경가"}

# 근무 패밀리 (인원 집계용)
D_FAMILY = [_D]            # D만
# M_FAMILY = [_D9, _D1, _M1, _M2]  # 중간 계열
E_FAMILY = [_E]            # E만
N_FAMILY = [_N]
WORK_INDICES = [_D, _E, _N]  # + M_FAMILY when 중간근무 추가

# 근무 순서 레벨 (역순 금지용)
SHIFT_LEVEL = {
    _D: 1,
    # _D9: 2, _D1: 2, _M1: 2, _M2: 2,  # 중간 계열
    _E: 2,   # → 3 when 중간근무 추가
    _N: 3,   # → 4 when 중간근무 추가
}

# 역순 금지 페어 (미리 계산)
FORBIDDEN_PAIRS = [
    (si, sj) for si in WORK_INDICES for sj in WORK_INDICES
    if SHIFT_LEVEL[si] > SHIFT_LEVEL[sj]
]
# → (N,D), (N,E), (E,D)


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
    # ni: 간호사 인덱스, di: 날짜(0-based), si: 타입(0~4)
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

    # num_weeks는 H11에서 일요일~토요일 기준으로 직접 계산

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
        model.add(
            sum(shifts[(ni, di, _D)] for ni in range(num_nurses))
            >= rules.daily_D
        )
        # M (중간 계열) — 중간근무 추가 시 활성화
        # model.add(
        #     sum(shifts[(ni, di, si)]
        #         for ni in range(num_nurses) for si in M_FAMILY)
        #     >= rules.daily_M
        # )
        model.add(
            sum(shifts[(ni, di, _E)] for ni in range(num_nurses))
            >= rules.daily_E
        )
        model.add(
            sum(shifts[(ni, di, _N)] for ni in range(num_nurses))
            >= rules.daily_N
        )

    # ── H3. 역순 금지 ──
    if rules.ban_reverse_order:
        for ni in range(num_nurses):
            for di in range(num_days - 1):
                for si, sj in FORBIDDEN_PAIRS:
                    model.add(
                        shifts[(ni, di, si)] + shifts[(ni, di + 1, sj)] <= 1
                    )

    # ── H4. 최대 연속 근무 (5일) ──
    # OFF와 LEAVE 모두 비근무로 인정
    max_cw = rules.max_consecutive_work
    for ni in range(num_nurses):
        for di in range(num_days - max_cw):
            model.add(
                sum(shifts[(ni, di + dd, _OFF)] + shifts[(ni, di + dd, _LEAVE)]
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
    # OFF와 LEAVE 모두 비근무로 인정
    off_after = rules.off_after_2N
    for ni in range(num_nurses):
        for di in range(num_days - 1):
            for k in range(off_after):
                if di + 2 + k < num_days:
                    model.add(
                        shifts[(ni, di, _N)] + shifts[(ni, di + 1, _N)] - 1
                        <= shifts[(ni, di + 2 + k, _OFF)]
                           + shifts[(ni, di + 2 + k, _LEAVE)]
                    )

    # ── H7. 월 N 제한 (6개) ──
    for ni in range(num_nurses):
        model.add(
            sum(shifts[(ni, di, _N)] for di in range(num_days))
            <= rules.max_N_per_month
        )

    # ── H8. 확정 요청 ──
    # 고정 주휴일에 LEAVE 요청이 겹치면 OFF 우선 (주휴 보장)
    fixed_off_days = set()  # (ni, di) 고정 주휴일
    for ni, nurse in enumerate(nurses):
        if nurse.fixed_weekly_off is not None:
            for di in range(num_days):
                if weekday_of(di) == nurse.fixed_weekly_off:
                    fixed_off_days.add((ni, di))

    for r in requests:
        if not r.is_hard:
            continue
        if r.nurse_id not in nurse_idx:
            continue
        ni = nurse_idx[r.nurse_id]
        di = r.day - 1
        if di < 0 or di >= num_days:
            continue
        # 고정 주휴일에 LEAVE 요청이 겹치면 OFF로 처리 (주휴 우선)
        if r.code in LEAVE_CODES and (ni, di) in fixed_off_days:
            model.add(shifts[(ni, di, _OFF)] == 1)
        elif r.code in LEAVE_CODES:
            model.add(shifts[(ni, di, _LEAVE)] == 1)
        else:
            # 주, OFF → 정규 휴무
            model.add(shifts[(ni, di, _OFF)] == 1)

    # ── H9. 제외 요청 ──
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
        # elif excluded == "M":  # 중간근무 추가 시
        #     for si in M_FAMILY:
        #         model.add(shifts[(ni, di, si)] == 0)
        elif excluded == "E":
            for si in E_FAMILY:
                model.add(shifts[(ni, di, si)] == 0)
        elif excluded == "N":
            model.add(shifts[(ni, di, _N)] == 0)

    # ── H10. 고정 주휴 ──
    for ni, nurse in enumerate(nurses):
        if nurse.fixed_weekly_off is not None:
            for di in range(num_days):
                if weekday_of(di) == nurse.fixed_weekly_off:
                    model.add(shifts[(ni, di, _OFF)] == 1)

    # ── H11. 주당 정규 휴무 (OFF만 카운트, LEAVE 제외) ──
    # 일반: OFF == 2/주 (주 1 + OFF 1)
    # 주4일제: OFF == 3/주 (주 1 + OFF 2)
    # 주 경계: 일요일~토요일 (weekday 6=일, 5=토)
    # LEAVE는 별도 추가 휴무이므로 이 제약에 포함하지 않음

    # 일요일~토요일 기준 주 경계 계산
    weeks = []  # list of (start_di, end_di) 0-based inclusive
    first_wd = weekday_of(0)  # 0=월..6=일
    # 일요일(6)이 주의 시작
    if first_wd == 6:
        wk_start = 0
    else:
        # 첫째 주: 1일 ~ 첫 토요일
        days_to_sat = (5 - first_wd) % 7
        first_sat = days_to_sat  # 0-based
        weeks.append((0, min(first_sat, num_days - 1)))
        wk_start = first_sat + 1

    while wk_start < num_days:
        wk_end = min(wk_start + 6, num_days - 1)
        weeks.append((wk_start, wk_end))
        wk_start = wk_end + 1

    for ni in range(num_nurses):
        base_min = rules.min_weekly_off          # 일반: 2
        if nurses[ni].is_4day_week:
            base_min = 3                          # 주4일제: 3
        for wk_start, wk_end in weeks:
            days_in_week = wk_end - wk_start + 1
            if days_in_week < 7:
                # 불완전 주: 비례 최소
                min_off = max(1, base_min * days_in_week // 7)
                model.add(
                    sum(shifts[(ni, di, _OFF)]
                        for di in range(wk_start, wk_end + 1))
                    >= min_off
                )
            else:
                model.add(
                    sum(shifts[(ni, di, _OFF)]
                        for di in range(wk_start, wk_end + 1))
                    == base_min
                )

    # ── H12. 책임 1명 이상 (매 근무) ──
    chiefs = [ni for ni, n in enumerate(nurses) if n.grade == "책임"]
    if chiefs and rules.min_chief_per_shift > 0:
        for di in range(num_days):
            for si in WORK_INDICES:
                model.add(
                    sum(shifts[(ni, di, si)] for ni in chiefs)
                    >= rules.min_chief_per_shift
                )

    # ── H13. 책임+서브차지 N명 이상 (매 근무) ──
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
    for tier_roles, max_d, max_e, max_n in ROLE_TIERS:
        tier_nurses = [ni for ni, n in enumerate(nurses)
                       if n.role in tier_roles]
        if not tier_nurses:
            continue
        for di in range(num_days):
            model.add(
                sum(shifts[(ni, di, _D)] for ni in tier_nurses) <= max_d
            )
            model.add(
                sum(shifts[(ni, di, _E)] for ni in tier_nurses) <= max_e
            )
            model.add(
                sum(shifts[(ni, di, _N)] for ni in tier_nurses) <= max_n
            )

    # ── H15. 책임만 1명 이하 (매 근무) ──
    chief_only = [ni for ni, n in enumerate(nurses)
                  if n.role == "책임만"]
    if chief_only:
        for di in range(num_days):
            for si in WORK_INDICES:
                model.add(
                    sum(shifts[(ni, di, si)] for ni in chief_only) <= 1
                )

    # ── (H16은 H11에 통합) ──

    # ── H17. 임산부 → 최대 연속 근무 4일 ──
    # OFF와 LEAVE 모두 비근무로 인정
    for ni, nurse in enumerate(nurses):
        if not nurse.is_pregnant:
            continue
        interval = rules.pregnant_poff_interval  # 4
        for di in range(num_days - interval):
            model.add(
                sum(shifts[(ni, di + dd, _OFF)] + shifts[(ni, di + dd, _LEAVE)]
                    for dd in range(interval + 1)) >= 1
            )

    # ══════════════════════════════════════════
    # LEAVE 자동 배정 (정확한 LEAVE 수 설정)
    # ══════════════════════════════════════════
    # 각 간호사별로 필요한 LEAVE 수를 정확히 계산하여 == 제약
    # (남는 LEAVE가 OFF로 변환되어 주당 OFF 초과하는 것 방지)
    for ni, nurse in enumerate(nurses):
        auto_leave = 0

        # L1. 여성 → 생휴용 LEAVE 1개 (이미 요청한 경우 제외)
        if not nurse.is_male and rules.menstrual_leave:
            has_menst_req = any(
                r.code == "생휴" and r.nurse_id == nurse.id
                for r in requests if r.is_hard
            )
            if not has_menst_req:
                auto_leave += 1

        # L2. 전월 미사용 수면 → 수면용 LEAVE 1개 (이미 요청한 경우 제외)
        if nurse.pending_sleep:
            has_sleep_req = any(
                r.code == "수면" and r.nurse_id == nurse.id
                for r in requests if r.is_hard
            )
            if not has_sleep_req:
                auto_leave += 1

        # 하드 요청으로 이미 강제된 LEAVE 수 (H8에서 처리됨)
        hard_leave_count = sum(
            1 for r in requests
            if r.is_hard and r.nurse_id == nurse.id
            and r.code in LEAVE_CODES
            and 1 <= r.day <= num_days
            and (ni, r.day - 1) not in fixed_off_days  # 주휴일 겹침 제외
        )

        total_leave = hard_leave_count + auto_leave

        # 정확히 필요한 만큼만 LEAVE 배치 (== 제약)
        model.add(
            sum(shifts[(ni, di, _LEAVE)] for di in range(num_days))
            == total_leave
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
            for si in WORK_INDICES:
                over = model.new_int_var(0, len(juniors), f"jr_d{di}_s{si}")
                jr_cnt = sum(shifts[(ni, di, si)] for ni in juniors)
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

        # 후처리: OFF/LEAVE 라벨링
        _post_process(schedule, nurses, requests, rules, year, month)

    return schedule


# ══════════════════════════════════════════
# 후처리: OFF → 주/OFF, LEAVE → 구체적 휴무 코드
# ══════════════════════════════════════════

def _post_process(
    schedule: Schedule,
    nurses: list[Nurse],
    requests: list[Request],
    rules: Rules,
    year: int,
    month: int,
):
    """솔버 결과의 OFF/LEAVE를 구체적 휴무 코드로 라벨링

    OFF 라벨링 (정규 휴무):
      1. 고정 주휴일 → 주
      2. 나머지 OFF → OFF 유지

    LEAVE 라벨링 (특수 휴무):
      1. 확정 요청이 있으면 → 요청 코드 (생휴, 수면, 법휴, 휴가, 공가, 경가)
      2. 생리휴무 (여성, 월 1개)
      3. 수면 (조건 충족 시)
      4. 임산부 POFF (4연속 근무 후)
      5. 나머지 LEAVE → OFF로 변환

    공휴일 보정: 공휴일의 비근무일(주 제외) → 법휴
    """
    num_days = schedule.num_days

    # 요청 맵: nurse_id → {day: Request}
    req_by_nurse = {}
    for r in requests:
        req_by_nurse.setdefault(r.nurse_id, {})[r.day] = r

    for nurse in nurses:
        nid = nurse.id
        nurse_reqs = req_by_nurse.get(nid, {})

        # ══ OFF 라벨링 ══

        # ── P1. 고정 주휴 라벨링 ──
        if nurse.fixed_weekly_off is not None:
            for day in range(1, num_days + 1):
                if schedule.weekday_index(day) == nurse.fixed_weekly_off:
                    if schedule.get_shift(nid, day) == "OFF":
                        schedule.set_shift(nid, day, "주")

        # ── P2. OFF 확정 요청 라벨링 (주, OFF 이외의 하드 요청) ──
        for day in range(1, num_days + 1):
            if schedule.get_shift(nid, day) != "OFF":
                continue
            r = nurse_reqs.get(day)
            if r and r.is_hard and r.code not in LEAVE_CODES:
                schedule.set_shift(nid, day, r.code)

        # ══ LEAVE 라벨링 ══

        # ── P3. LEAVE 확정 요청 라벨링 ──
        for day in range(1, num_days + 1):
            if schedule.get_shift(nid, day) != "LEAVE":
                continue
            r = nurse_reqs.get(day)
            if r and r.is_hard and r.code in LEAVE_CODES:
                schedule.set_shift(nid, day, r.code)

        # ── P4. 생리휴무 (남자 제외, 월 1개) ──
        if not nurse.is_male and rules.menstrual_leave:
            already = any(
                schedule.get_shift(nid, d) == "생휴"
                for d in range(1, num_days + 1)
            )
            if not already:
                for day in range(1, num_days + 1):
                    if schedule.get_shift(nid, day) == "LEAVE":
                        schedule.set_shift(nid, day, "생휴")
                        break  # 월 1개만

        # ── P5. 수면 라벨링 ──
        _label_sleep(schedule, nurse, rules, year, month)

        # ── P6. 임산부 POFF 라벨링 ──
        if nurse.is_pregnant:
            _label_poff(schedule, nurse, rules)

        # ── P7. 남은 LEAVE → OFF로 변환 ──
        for day in range(1, num_days + 1):
            if schedule.get_shift(nid, day) == "LEAVE":
                schedule.set_shift(nid, day, "OFF")

        # ── P8. 공휴일 최종 보정: 주 빼고 모든 비근무 → 법휴 ──
        for day in rules.public_holidays:
            if day < 1 or day > num_days:
                continue
            s = schedule.get_shift(nid, day)
            if s not in WORK_SHIFTS and s != "주":
                schedule.set_shift(nid, day, "법휴")


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
    - 짝수월: 전월+당월 N 합산 >= 11
    - 전월 미사용 수면(pending_sleep) 이월

    LEAVE → 수면 우선, 없으면 OFF → 수면 (fallback)
    """
    nid = nurse.id
    num_days = schedule.num_days

    needs_sleep = False
    sleep_available_from = 1

    # 전월 미사용 수면 → 1일부터 사용 가능
    if nurse.pending_sleep:
        needs_sleep = True
        sleep_available_from = 1

    # 2개월 페어 체크
    partner = get_sleep_partner_month(month)

    # 당월 N 누적
    n_cumulative = 0
    for day in range(1, num_days + 1):
        if schedule.get_shift(nid, day) == "N":
            n_cumulative += 1

        if n_cumulative >= rules.sleep_N_monthly and not needs_sleep:
            needs_sleep = True
            sleep_available_from = day + 1

        if partner is not None and not needs_sleep:
            total_n = nurse.prev_month_N + n_cumulative
            if total_n >= rules.sleep_N_bimonthly:
                needs_sleep = True
                sleep_available_from = day + 1

    if not needs_sleep:
        return

    # 수면 배정: LEAVE 우선, OFF fallback
    for target in ["LEAVE", "OFF"]:
        for day in range(sleep_available_from, num_days + 1):
            if schedule.get_shift(nid, day) == target:
                schedule.set_shift(nid, day, "수면")
                return


def _label_poff(schedule: Schedule, nurse: Nurse, rules: Rules):
    """임산부 POFF 라벨링

    4연속 근무 후 첫 LEAVE를 POFF로 라벨링
    LEAVE 없으면 OFF를 POFF로 (fallback)
    """
    nid = nurse.id
    num_days = schedule.num_days
    interval = rules.pregnant_poff_interval  # 4

    consecutive_work = 0
    for day in range(1, num_days + 1):
        s = schedule.get_shift(nid, day)
        if s in WORK_SHIFTS:
            consecutive_work += 1
        elif consecutive_work >= interval and s in ("LEAVE", "OFF"):
            schedule.set_shift(nid, day, "POFF")
            consecutive_work = 0
        else:
            consecutive_work = 0
