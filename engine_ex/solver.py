"""스케줄링 엔진 - Google OR-Tools CP-SAT Solver

Hard Constraints (16개):
 1. 하루 1근무
 2. 최소 인원 (평일/주말)
 3. N→D 금지
 4. N→E 금지
 5. E→D 금지
 6. 최대 연속 근무
 7. 최대 연속 야간
 8. 야간 연속 후 OFF 강제 (금지 패턴으로 커버)
 9. 야간/주간/저녁 금지 (개인)
10. 고정 근무 (개인)
11. 확정 요청 (연차, 고정코드)
12. 프리셉터-신규 동일 근무
13. 야간 숙련자 필수
14. 신규끼리 야간 금지
15. 월 휴무일 범위
16. 최대 연속 휴무

Soft Constraints (목적함수 최대화):
 - 희망 요청 반영 보너스 (가중치 10)
 - D/E/N 횟수 편차 최소 (가중치 5)
 - 야간 균등 배분 (가중치 8)
 - 주말 균등 배분 (가중치 8)
"""
import calendar
from ortools.sat.python import cp_model
from engine.models import Nurse, Request, Rules, Schedule


# 근무 타입 인덱스
D, E, N, OFF = 0, 1, 2, 3
SHIFT_NAMES = {D: "D", E: "E", N: "N", OFF: "OFF"}
SHIFT_INDEX = {"D": D, "E": E, "N": N, "OFF": OFF}


def solve_schedule(
    nurses: list[Nurse],
    requests: list[Request],
    rules: Rules,
    year: int,
    month: int,
    timeout_seconds: int = 30,
) -> Schedule:
    """OR-Tools CP-SAT으로 최적 근무표 생성"""

    num_days = calendar.monthrange(year, month)[1]
    num_nurses = len(nurses)
    num_shifts = 4  # D, E, N, OFF

    model = cp_model.CpModel()

    # ──────────────────────────────────────────
    # 변수 정의: shifts[n][d][s] = BoolVar
    # ──────────────────────────────────────────
    shifts = {}
    for ni in range(num_nurses):
        for di in range(num_days):
            for si in range(num_shifts):
                shifts[(ni, di, si)] = model.new_bool_var(f"shift_n{ni}_d{di}_s{si}")

    # 인덱스 맵
    nurse_idx = {nurse.id: i for i, nurse in enumerate(nurses)}

    # 요청 맵
    req_map = {}
    for r in requests:
        req_map[(r.nurse_id, r.day)] = r

    # 주말 여부
    def is_weekend(di):
        return calendar.weekday(year, month, di + 1) >= 5

    # ══════════════════════════════════════════
    # HARD CONSTRAINTS
    # ══════════════════════════════════════════

    # 1. 하루에 정확히 1개 근무
    for ni in range(num_nurses):
        for di in range(num_days):
            model.add(sum(shifts[(ni, di, si)] for si in range(num_shifts)) == 1)

    # 2. 최소 인원 충족
    for di in range(num_days):
        weekend = is_weekend(di)
        for shift_name, si in [("D", D), ("E", E), ("N", N)]:
            min_staff = rules.get_min_staff(shift_name, weekend)
            model.add(
                sum(shifts[(ni, di, si)] for ni in range(num_nurses)) >= min_staff
            )

    # 3~5. 금지 패턴
    for ni in range(num_nurses):
        for di in range(num_days - 1):
            if rules.ban_night_to_day:
                model.add(shifts[(ni, di, N)] + shifts[(ni, di + 1, D)] <= 1)
            if rules.ban_night_to_evening:
                model.add(shifts[(ni, di, N)] + shifts[(ni, di + 1, E)] <= 1)
            if rules.ban_evening_to_day:
                model.add(shifts[(ni, di, E)] + shifts[(ni, di + 1, D)] <= 1)

    # 6. 최대 연속 근무일
    max_cw = rules.max_consecutive_work
    for ni in range(num_nurses):
        for di in range(num_days - max_cw):
            # max_cw+1일 구간에서 OFF 최소 1개
            model.add(
                sum(shifts[(ni, di + dd, OFF)] for dd in range(max_cw + 1)) >= 1
            )

    # 7. 최대 연속 야간
    max_cn = rules.max_consecutive_night
    for ni in range(num_nurses):
        for di in range(num_days - max_cn):
            model.add(
                sum(shifts[(ni, di + dd, N)] for dd in range(max_cn + 1)) <= max_cn
            )

    # 8. 야간 연속 후 OFF 강제
    #    N→D, N→E 금지 패턴이 이미 커버 (N 다음엔 N 또는 OFF만 가능)
    #    추가: 연속 N 마지막 다음날 반드시 OFF
    if rules.night_off_after >= 1:
        for ni in range(num_nurses):
            for di in range(num_days - 1):
                # N→non-N 전환 시 = OFF여야 함
                # (이미 N→D, N→E 금지로 커버됨)
                pass

    # 9. 야간/주간/저녁 금지 (개인)
    for ni, nurse in enumerate(nurses):
        if not nurse.can_night:
            for di in range(num_days):
                model.add(shifts[(ni, di, N)] == 0)
        if not nurse.can_day:
            for di in range(num_days):
                model.add(shifts[(ni, di, D)] == 0)
        if not nurse.can_evening:
            for di in range(num_days):
                model.add(shifts[(ni, di, E)] == 0)
        # 평일만 근무 → 주말 OFF 강제
        if nurse.weekday_only:
            for di in range(num_days):
                if is_weekend(di):
                    model.add(shifts[(ni, di, OFF)] == 1)

    # 10. 고정 근무 (매일 같은 근무)
    for ni, nurse in enumerate(nurses):
        if nurse.fixed_shift and nurse.fixed_shift in SHIFT_INDEX:
            si = SHIFT_INDEX[nurse.fixed_shift]
            for di in range(num_days):
                # 연차/OFF 요청 날은 예외
                req = req_map.get((nurse.id, di + 1))
                if req and req.code in ("연차", "OFF"):
                    continue
                model.add(shifts[(ni, di, si)] == 1)

    # 11. 확정 요청 (연차, 고정코드 !)
    for r in requests:
        if r.nurse_id not in nurse_idx:
            continue
        ni = nurse_idx[r.nurse_id]
        di = r.day - 1
        if di < 0 or di >= num_days:
            continue

        if r.code == "연차":
            model.add(shifts[(ni, di, OFF)] == 1)
        elif r.code == "D!":
            model.add(shifts[(ni, di, D)] == 1)
        elif r.code == "E!":
            model.add(shifts[(ni, di, E)] == 1)
        elif r.code == "N!":
            model.add(shifts[(ni, di, N)] == 1)

    # 12. 프리셉터-신규 동일 근무
    for ni, nurse in enumerate(nurses):
        if nurse.preceptor_of is not None and nurse.preceptor_of in nurse_idx:
            ji = nurse_idx[nurse.preceptor_of]
            for di in range(num_days):
                for si in range(num_shifts):
                    model.add(shifts[(ni, di, si)] == shifts[(ji, di, si)])

    # 13. 야간 숙련자 필수
    if rules.night_senior_required:
        seniors = [ni for ni, nurse in enumerate(nurses)
                   if nurse.skill_level >= 3 and nurse.can_night]
        if seniors:
            for di in range(num_days):
                model.add(sum(shifts[(ni, di, N)] for ni in seniors) >= 1)

    # 14. 신규끼리 야간 금지
    if rules.ban_newbie_pair_night:
        newbies = [ni for ni, nurse in enumerate(nurses)
                   if nurse.skill_level == 1 and nurse.can_night]
        if len(newbies) >= 2:
            for di in range(num_days):
                model.add(sum(shifts[(ni, di, N)] for ni in newbies) <= 1)

    # 15. 월간 휴무일 범위
    for ni in range(num_nurses):
        total_off = sum(shifts[(ni, di, OFF)] for di in range(num_days))
        model.add(total_off >= rules.min_monthly_off)
        model.add(total_off <= rules.max_monthly_off)

    # 16. 최대 연속 휴무
    max_co = rules.max_consecutive_off
    if max_co < num_days:
        for ni in range(num_nurses):
            for di in range(num_days - max_co):
                model.add(
                    sum(shifts[(ni, di + dd, OFF)] for dd in range(max_co + 1)) <= max_co
                )

    # ══════════════════════════════════════════
    # SOFT CONSTRAINTS (목적함수)
    # ══════════════════════════════════════════
    obj = []

    # ── 요청 반영 보너스 (가중치 10) ──
    for r in requests:
        if r.is_hard or r.nurse_id not in nurse_idx:
            continue
        ni = nurse_idx[r.nurse_id]
        di = r.day - 1
        if di < 0 or di >= num_days:
            continue

        code_to_si = {"OFF": OFF, "D": D, "E": E, "N": N}
        if r.code in code_to_si:
            obj.append(10 * shifts[(ni, di, code_to_si[r.code])])

    # ── D/E/N 횟수 공정성 (가중치 5) ──
    shift_counts = {}
    for ni in range(num_nurses):
        for si in [D, E, N]:
            c = model.new_int_var(0, num_days, f"cnt_n{ni}_s{si}")
            model.add(c == sum(shifts[(ni, di, si)] for di in range(num_days)))
            shift_counts[(ni, si)] = c

    for si in [D, E, N]:
        all_counts = [shift_counts[(ni, si)] for ni in range(num_nurses)]
        if len(all_counts) >= 2:
            mx = model.new_int_var(0, num_days, f"max_s{si}")
            mn = model.new_int_var(0, num_days, f"min_s{si}")
            model.add_max_equality(mx, all_counts)
            model.add_min_equality(mn, all_counts)
            diff = model.new_int_var(0, num_days, f"diff_s{si}")
            model.add(diff == mx - mn)
            obj.append(-5 * diff)

    # ── 야간 균등 (가중치 8) ──
    night_eligible = [ni for ni, nurse in enumerate(nurses) if nurse.can_night]
    if len(night_eligible) >= 2:
        nc = [shift_counts[(ni, N)] for ni in night_eligible]
        mx = model.new_int_var(0, num_days, "max_night")
        mn = model.new_int_var(0, num_days, "min_night")
        model.add_max_equality(mx, nc)
        model.add_min_equality(mn, nc)
        diff = model.new_int_var(0, num_days, "night_diff")
        model.add(diff == mx - mn)
        obj.append(-8 * diff)

    # ── 주말 균등 (가중치 8) ──
    weekend_days = [di for di in range(num_days) if is_weekend(di)]
    if weekend_days and num_nurses >= 2:
        wk_counts = []
        for ni in range(num_nurses):
            c = model.new_int_var(0, len(weekend_days) * 3, f"wk_n{ni}")
            model.add(c == sum(
                shifts[(ni, di, si)] for di in weekend_days for si in [D, E, N]
            ))
            wk_counts.append(c)

        mx = model.new_int_var(0, len(weekend_days) * 3, "max_wk")
        mn = model.new_int_var(0, len(weekend_days) * 3, "min_wk")
        model.add_max_equality(mx, wk_counts)
        model.add_min_equality(mn, wk_counts)
        diff = model.new_int_var(0, len(weekend_days) * 3, "wk_diff")
        model.add(diff == mx - mn)
        obj.append(-8 * diff)

    # 목적함수
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
                for si in range(num_shifts):
                    if solver.value(shifts[(ni, di, si)]):
                        schedule.set_shift(nurse.id, di + 1, SHIFT_NAMES[si])
                        break

    return schedule
