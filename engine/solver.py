"""스케줄링 엔진 - Google OR-Tools CP-SAT Solver
응급실 간호사 근무표 생성

13개 타입(D/E/N/주/OFF/법휴/수면/생휴/휴가/특휴/공가/경가/보수)을 솔버 변수로 직접 사용.

휴무 구조:
 정규 (주당 예산): 주(1/주, 고정요일) + OFF(1/주, 비고정) = 2/주
 추가 (예산 외):
 - 법휴: 공휴일에만 배치, 공휴일에 주휴 외 모든 off → 법휴
 - 수면: N 조건 충족 다음날부터 사용 (pending_sleep/monthly/bimonthly)
 - 생휴: 여성 월 1회, 사용 못하면 소멸 (soft)
 - POFF: 임산부 4연속 근무 후 (후처리)
 - 휴가: 개인 잔여에서 차감, 요청 시만
 - 보수/공가/경가: 요청 시만
 우선순위: 주/OFF → 수면/생휴 → 요청 → 휴가

Hard Constraints:
 H1.  하루 1배정 (12타입 중 1개)
 H2.  일일 인원 (D/E/N 최소)
 H3.  역순 금지 (D→E→N)
 H4.  최대 연속 근무 (5일)
 H5.  최대 연속 N (3개)
 H6.  N 2연속 후 휴무 2개
 H7.  월 N 제한 (6개)
 H8.  확정 요청 직접 매핑
 H9.  제외 요청
 H10. 고정 주휴 + 주 배치 제한 (고정일만) + 법휴 배치 제한 (공휴일만)
 H11. 주당 정규 휴무 (주+OFF == 2, 주4일제 == 3)
 H12. 책임 1명 이상
 H13. 책임+서브차지 N명 이상
 H14. 역할 누적 제한
 H15. 책임만 1명 이하
 H17. 임산부 4연속 근무 제한
 H18. 공휴일 → 주휴 외 off는 법휴만
 수면 조건부 (N 임계값 + 타이밍)
 생휴/휴가/특휴/공가/경가/보수 갯수 제약

Soft Constraints:
 S1. 희망 요청 반영 (+10)
 S2. D/E/N 횟수 공정 (-5)
 S3. N 균등 배분 (-8)
 S4. 주말 균등 배분 (-8)
 S5. 일반 3명 이하 권고 (-3)
 S6. 생휴 배정 유도 (+20, 여성)

후처리:
 P1. 임산부 POFF: 4연속 근무 후 첫 휴무 → POFF 리라벨
"""
import calendar
from ortools.sat.python import cp_model
from engine.models import (
    Nurse, Request, Rules, Schedule,
    WORK_SHIFTS, OFF_TYPES, SHIFT_ORDER, ROLE_TIERS,
    get_sleep_partner_month,
)


# ══════════════════════════════════════════
# 솔버 내 근무 타입 인덱스 (12개)
# ══════════════════════════════════════════

# 근무
_D, _E, _N = 0, 1, 2
# _D, _D9, _D1, _M1, _M2, _E, _N = 0, 1, 2, 3, 4, 5, 6

# 휴무 (개별 타입)
_주 = 3
_OFF = 4
_법휴 = 5
_수면 = 6
_생휴 = 7
_휴가 = 8
_특휴 = 9
_공가 = 10
_경가 = 11
_보수 = 12

NUM_TYPES = 13

# 인덱스 ↔ 이름
IDX_TO_NAME = {
    _D: "D",
    # _D9: "D9", _D1: "D1", _M1: "중1", _M2: "중2",
    _E: "E", _N: "N",
    _주: "주", _OFF: "OFF", _법휴: "법휴", _수면: "수면",
    _생휴: "생휴", _휴가: "휴가", _특휴: "특휴", _공가: "공가", _경가: "경가",
    _보수: "보수",
}
NAME_TO_IDX = {v: k for k, v in IDX_TO_NAME.items()}

# 휴무 그룹
REGULAR_OFF = [_주, _OFF]                                               # 주당 정규 휴무 (주1 + OFF1 = 2)
EXTRA_OFF = [_법휴, _수면, _생휴, _휴가, _특휴, _공가, _경가, _보수]     # 추가 휴무 (주당 예산 외)
ALL_OFF = REGULAR_OFF + EXTRA_OFF                                       # 연속근무 중단 인정 대상

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
    # ni: 간호사 인덱스, di: 날짜(0-based), si: 타입(0~11)
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
    # ALL_OFF 모두 비근무로 인정
    max_cw = rules.max_consecutive_work
    for ni in range(num_nurses):
        for di in range(num_days - max_cw):
            model.add(
                sum(shifts[(ni, di + dd, oi)]
                    for dd in range(max_cw + 1) for oi in ALL_OFF) >= 1
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
    # ALL_OFF 모두 비근무로 인정
    off_after = rules.off_after_2N
    for ni in range(num_nurses):
        for di in range(num_days - 1):
            for k in range(off_after):
                if di + 2 + k < num_days:
                    model.add(
                        shifts[(ni, di, _N)] + shifts[(ni, di + 1, _N)] - 1
                        <= sum(shifts[(ni, di + 2 + k, oi)] for oi in ALL_OFF)
                    )

    # ── H7. 월 N 제한 (6개) ──
    for ni in range(num_nurses):
        model.add(
            sum(shifts[(ni, di, _N)] for di in range(num_days))
            <= rules.max_N_per_month
        )

    # ── H8. 확정 요청 ──
    # 각 요청 코드를 해당 인덱스로 직접 매핑
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
        # 고정 주휴일에 특수 휴무 요청이 겹치면 주휴 우선
        if r.code in NAME_TO_IDX and r.code not in ("D", "E", "N") and (ni, di) in fixed_off_days:
            model.add(shifts[(ni, di, _주)] == 1)
        elif r.code in NAME_TO_IDX:
            si = NAME_TO_IDX[r.code]
            model.add(shifts[(ni, di, si)] == 1)

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
                    model.add(shifts[(ni, di, _주)] == 1)

    # ── H10a. 주는 고정 주휴일에만 배치 가능 ──
    for ni, nurse in enumerate(nurses):
        for di in range(num_days):
            if nurse.fixed_weekly_off is None or weekday_of(di) != nurse.fixed_weekly_off:
                model.add(shifts[(ni, di, _주)] == 0)

    # ── H10b. 법휴는 공휴일에만 배치 가능 ──
    public_holiday_dis = set(h - 1 for h in rules.public_holidays if 1 <= h <= num_days)
    for ni in range(num_nurses):
        for di in range(num_days):
            if di not in public_holiday_dis:
                model.add(shifts[(ni, di, _법휴)] == 0)

    # ── H11. 주당 정규 휴무 (주+OFF 카운트) ──
    # 일반: 주+OFF == 2/주 (주1 + OFF1)
    # 주4일제: 주+OFF == 3/주
    # 법휴/수면/생휴 등은 별도 추가 (이 예산에 미포함)
    # 주 경계: 일요일~토요일 (weekday 6=일, 5=토)

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
                    sum(shifts[(ni, di, oi)]
                        for di in range(wk_start, wk_end + 1)
                        for oi in REGULAR_OFF)
                    >= min_off
                )
            else:
                model.add(
                    sum(shifts[(ni, di, oi)]
                        for di in range(wk_start, wk_end + 1)
                        for oi in REGULAR_OFF)
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
    # ALL_OFF 모두 비근무로 인정
    for ni, nurse in enumerate(nurses):
        if not nurse.is_pregnant:
            continue
        interval = rules.pregnant_poff_interval  # 4
        for di in range(num_days - interval):
            model.add(
                sum(shifts[(ni, di + dd, oi)]
                    for dd in range(interval + 1) for oi in ALL_OFF) >= 1
            )

    # ══════════════════════════════════════════
    # 특수 휴무 갯수 제약 (타입별 정확한 수 강제)
    # ══════════════════════════════════════════
    obj_auto_off = []  # 생휴 soft bonus (목적함수에 추가)
    for ni, nurse in enumerate(nurses):
        # 각 특수 off 타입별 하드 요청 갯수 계산
        hard_counts = {}
        for code, idx in [("생휴", _생휴), ("수면", _수면), ("휴가", _휴가),
                          ("특휴", _특휴), ("공가", _공가), ("경가", _경가),
                          ("보수", _보수)]:
            hard_counts[idx] = sum(
                1 for r in requests
                if r.is_hard and r.nurse_id == nurse.id
                and r.code == code
                and 1 <= r.day <= num_days
                and (ni, r.day - 1) not in fixed_off_days
            )

        # 생휴: 여성 월 1회, 사용 못하면 소멸 (hard req 있으면 그 갯수)
        hard_menst = hard_counts[_생휴]
        menst_sum = sum(shifts[(ni, di, _생휴)] for di in range(num_days))
        if hard_menst > 0:
            model.add(menst_sum == hard_menst)
        elif not nurse.is_male and rules.menstrual_leave:
            # <= 1 (소멸 가능), soft로 1개 배정 유도
            model.add(menst_sum <= 1)
            menst_bonus = model.new_bool_var(f"menst_{ni}")
            model.add(menst_sum == 1).only_enforce_if(menst_bonus)
            model.add(menst_sum == 0).only_enforce_if(menst_bonus.Not())
            obj_auto_off.append(20 * menst_bonus)
        else:
            model.add(menst_sum == 0)

        # 수면: 조건 충족 시 1개 생성, 마지막 N 다음날부터 사용 가능
        # 당월 배치 불가 시 이월 (pending_sleep → 다음달)
        hard_sleep = hard_counts[_수면]
        sleep_sum = sum(shifts[(ni, di, _수면)] for di in range(num_days))
        if hard_sleep > 0:
            # 하드 요청이 있으면 그 갯수만큼 (H8이 배치 처리)
            model.add(sleep_sum == hard_sleep)
        elif nurse.pending_sleep:
            # 전월 이월 수면 → 1개, 1일부터 사용 가능 (타이밍 제약 없음)
            model.add(sleep_sum == 1)
        else:
            # 조건부: N 누적이 임계값 도달 시 당월 배치 시도
            # 짝수월: effective = min(monthly, bimonthly - prev_N)
            # 홀수월: effective = monthly
            partner = get_sleep_partner_month(month)
            eff_threshold = rules.sleep_N_monthly  # 기본 7
            if partner is not None:
                bimonthly_eff = max(0, rules.sleep_N_bimonthly - nurse.prev_month_N)
                eff_threshold = min(eff_threshold, bimonthly_eff)

            if eff_threshold <= 0:
                # 이미 조건 충족 (prev_N만으로 충분) → 1개, 타이밍 제약 없음
                model.add(sleep_sum == 1)
            elif eff_threshold > rules.max_N_per_month:
                # 도달 불가 (monthly 7 > max_N 6 등) → 0개
                model.add(sleep_sum == 0)
            else:
                # 조건부: N >= threshold 이면 당월 배치 시도 (soft)
                # 배치 못하면 0 → 후처리에서 이월 처리
                total_N_var = model.new_int_var(0, num_days, f"totalN_{ni}")
                model.add(total_N_var == sum(
                    shifts[(ni, di, _N)] for di in range(num_days)
                ))

                sleep_needed = model.new_bool_var(f"sleepNeed_{ni}")
                model.add(
                    total_N_var >= eff_threshold
                ).only_enforce_if(sleep_needed)
                model.add(
                    total_N_var <= eff_threshold - 1
                ).only_enforce_if(sleep_needed.Not())

                # 조건 미충족 → 0개 (hard)
                # 조건 충족 → <= 1 (soft, 당월 배치 시도)
                model.add(sleep_sum == 0).only_enforce_if(sleep_needed.Not())
                model.add(sleep_sum <= 1).only_enforce_if(sleep_needed)

                # soft: 조건 충족 시 당월 배치 유도 (+30)
                sleep_placed = model.new_bool_var(f"sleepPlaced_{ni}")
                model.add(sleep_sum == 1).only_enforce_if(sleep_placed)
                model.add(sleep_sum == 0).only_enforce_if(sleep_placed.Not())
                obj_auto_off.append(30 * sleep_placed)

                # 타이밍: 수면 배치일 이전까지 누적 N >= threshold
                for di in range(num_days):
                    if di < eff_threshold:
                        # 이 날짜 이전에 threshold개 N 불가능 → 수면 금지
                        model.add(shifts[(ni, di, _수면)] == 0)
                    else:
                        # 수면이 이 날에 배치되면, 이전 누적 N >= threshold
                        model.add(
                            sum(shifts[(ni, dd, _N)] for dd in range(di))
                            >= eff_threshold
                        ).only_enforce_if(shifts[(ni, di, _수면)])

        # 휴가, 특휴, 공가, 경가, 보수: == hard_request_count (요청 시만)
        for idx in [_휴가, _특휴, _공가, _경가, _보수]:
            model.add(
                sum(shifts[(ni, di, idx)] for di in range(num_days))
                == hard_counts[idx]
            )

        # 법휴: 갯수 고정 안 함 (H18 공휴일 제약이 결정)

    # ── H18. 공휴일 → 비근무 시 법휴만 허용 ──
    # 공휴일에 고정주휴도 아니고 특정 요청도 없는 경우:
    # 근무(D/E/N) 또는 법휴만 가능
    hard_req_days = set()  # (ni, di) 하드 요청이 있는 날
    for r in requests:
        if r.is_hard and r.nurse_id in nurse_idx:
            ni_r = nurse_idx[r.nurse_id]
            di_r = r.day - 1
            if 0 <= di_r < num_days:
                hard_req_days.add((ni_r, di_r))

    for hday in rules.public_holidays:
        di = hday - 1
        if di < 0 or di >= num_days:
            continue
        for ni in range(num_nurses):
            # 고정 주휴일이면 스킵 (H10이 이미 _주 강제)
            if (ni, di) in fixed_off_days:
                continue
            # 하드 요청이 있으면 스킵 (H8이 이미 처리)
            if (ni, di) in hard_req_days:
                continue
            # 법휴 외의 모든 off 타입 금지 → 근무 또는 법휴만 가능
            for oi in ALL_OFF:
                if oi != _법휴:
                    model.add(shifts[(ni, di, oi)] == 0)

    # ══════════════════════════════════════════
    # SOFT CONSTRAINTS (목적함수)
    # ══════════════════════════════════════════
    obj = list(obj_auto_off)  # 생휴 soft bonus 포함

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
            # OFF 요청 → 어떤 off 타입이든 쉬면 충족
            obj.append(10 * sum(shifts[(ni, di, oi)] for oi in ALL_OFF))
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

        # 후처리: 임산부 POFF 리라벨
        _post_process(schedule, nurses, rules)

    return schedule


# ══════════════════════════════════════════
# 후처리: 임산부 POFF 리라벨만
# ══════════════════════════════════════════

def _post_process(
    schedule: Schedule,
    nurses: list[Nurse],
    rules: Rules,
):
    """솔버 결과 후 임산부 POFF 리라벨

    4연속 근무 후 첫 휴무 → POFF로 리라벨
    """
    for nurse in nurses:
        if nurse.is_pregnant:
            _label_poff(schedule, nurse, rules)


def _label_poff(schedule: Schedule, nurse: Nurse, rules: Rules):
    """임산부 POFF 리라벨

    4연속 근무 후 첫 휴무(어떤 off 타입이든) → POFF로 리라벨
    """
    nid = nurse.id
    num_days = schedule.num_days
    interval = rules.pregnant_poff_interval  # 4

    consecutive_work = 0
    for day in range(1, num_days + 1):
        s = schedule.get_shift(nid, day)
        if s in WORK_SHIFTS:
            consecutive_work += 1
        elif consecutive_work >= interval and s not in WORK_SHIFTS:
            schedule.set_shift(nid, day, "POFF")
            consecutive_work = 0
        else:
            consecutive_work = 0
