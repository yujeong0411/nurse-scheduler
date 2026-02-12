"""스케줄링 엔진 - Google OR-Tools CP-SAT Solver
응급실 간호사 근무표 생성

14개 타입(D/E/N/주/OFF/법휴/수면/생휴/휴가/특휴/공가/경가/보수/POFF)을 솔버 변수로 사용.
모든 휴무 타입을 솔버가 직접 관리하여 최적 배치.

원칙:
 - D/E/N 인원은 == (정확히 고정)
 - 나머지 인원은 자동으로 휴무 (타입도 솔버가 결정)
 - 휴무 우선순위: 주(1/주) → OFF(1/주) → 수면 → 생휴 → 나머지(휴가)

Hard Constraints:
 H1.  하루 1배정
 H2.  일일 인원 (D/E/N == 고정)
 H3.  역순 금지 (D→E→N)
 H3a. N→1off→D 금지 (N 후 D까지 최소 2일 휴무)
 H4.  최대 연속 근무 (5일)
 H5.  최대 연속 N (3개)
 H6.  N 2연속 후 휴무 2개
 H7.  월 N 제한 (6개)
 H8.  확정 요청 직접 매핑
 H9.  제외 요청
 H10. 고정 주휴 (고정요일에 주 배정)
 H10a. 주는 고정 주휴일에만 배치 가능
 H10b. 법휴는 공휴일에만 배치 가능
 H11. 주당 OFF 1개 (완전한 주 기준)
 H12. 책임 1명 이상
 H13. 책임+서브차지 N명 이상
 H14. 역할 누적 제한
 H15. 책임만 1명 이하
 H17. 임산부 4연속 근무 제한
 H18. 공휴일 비근무 시 법휴만 허용 (고정주휴/하드요청 제외)
 H19. 임산부 POFF: 4연속 근무 후 추가 휴무
 H20. 휴무 편차 제한 (일반 ±2, 주4일제 +4)
 특수 휴무 갯수 (생휴/수면 조건부 하드, 특휴/공가/경가/보수 하드요청분, 휴가 catch-all)

Soft Constraints:
 S1. 희망 요청 반영 (+30)
 S2. D/E/N 횟수 공정 (-5)
 S3. N 균등 배분 (-8)
 S4. 주말 균등 배분 (-8)
 S5. 일반 3명 이하 권고 (-3)
"""
from datetime import date, timedelta
from ortools.sat.python import cp_model
from engine.models import (
    Nurse, Request, Rules, Schedule, ROLE_TIERS, get_sleep_partner_month
)
from datetime import datetime
def _log(message):
    """실행 파일 위치에 crash.log 파일을 생성하여 로그를 기록합니다."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_msg = f"[{timestamp}] {message}\n"
    print(log_msg)  # 터미널에도 출력
    
    # EXE 실행 시에도 찾기 쉬운 위치(바탕화면이나 프로그램 폴더)에 로그 생성
    with open("solver_debug.log", "a", encoding="utf-8") as f:
        f.write(log_msg)


# ══════════════════════════════════════════
# 솔버 내 근무 타입 인덱스 (12개)
# ══════════════════════════════════════════

# 근무
_D, _중2, _E, _N = 0, 1, 2, 3
# _D, _D9, _D1, _중1, _중2, _E, _N = 0, 1, 2, 3, 4, 5, 6

# 휴무 (개별 타입) — _N=3 다음부터 시작
_주 = 4
_OFF = 5
_법휴 = 6
_수면 = 7
_생휴 = 8
_휴가 = 9
_특휴 = 10
_공가 = 11
_경가 = 12
_보수 = 13
_POFF = 14

NUM_TYPES = 15

# 인덱스 ↔ 이름
IDX_TO_NAME = {
    _D: "D",
    _중2: "중2",
    # _D9: "D9", _D1: "D1", _중1: "중1",
    _E: "E", _N: "N",
    _주: "주", _OFF: "OFF", _법휴: "법휴", _수면: "수면",
    _생휴: "생휴", _휴가: "휴가", _특휴: "특휴", _공가: "공가", _경가: "경가",
    _보수: "보수", _POFF: "POFF",
}
NAME_TO_IDX = {v: k for k, v in IDX_TO_NAME.items()}

# 휴무 그룹
REGULAR_OFF = [_주, _OFF]                                               # 주당 정규 휴무 (주1 + OFF1 = 2)
EXTRA_OFF = [_법휴, _수면, _생휴, _휴가, _특휴, _공가, _경가, _보수, _POFF]  # 추가 휴무 (주당 예산 외)
ALL_OFF = REGULAR_OFF + EXTRA_OFF                                       # 연속근무 중단 인정 대상

# 근무 패밀리 (인원 집계용)
D_FAMILY = [_D]            # D만
M_FAMILY = [_중2]  # 중간 계열   _D9, _D1, _중1 추후 추가
E_FAMILY = [_E]            # E만
N_FAMILY = [_N]
WORK_INDICES = [_D, _E, _N, _중2]  # + M_FAMILY when 중간근무 추가

# 근무 순서 레벨 (역순 금지용)
SHIFT_LEVEL = {
    _D: 1,
    _중2: 2,
    # _D9: 2, _D1: 2, _중1: 2,  # 중간 계열
    _E: 3,
    _N: 4,
}

# 역순 금지 페어 (미리 계산)
FORBIDDEN_PAIRS = [
    (si, sj) for si in WORK_INDICES for sj in WORK_INDICES
    if SHIFT_LEVEL[si] > SHIFT_LEVEL[sj]
]
# → (N,D), (N,중2), (N,E), (E,D), (E,중2), (중2,D)


def solve_schedule(
    nurses: list[Nurse],
    requests: list[Request],
    rules: Rules,
    start_date: date,
    timeout_seconds: int = 180,
    output_path: str = None  # 경로 파라미터 추가
) -> Schedule:
    """OR-Tools CP-SAT으로 최적 근무표 생성 (4주=28일 고정)"""

    num_days = 28
    num_nurses = len(nurses)
    model = cp_model.CpModel()

    # ──────────────────────────────────────────
    # 변수 정의: shifts[(ni, di, si)] = BoolVar
    # ni: 간호사 인덱스, di: 날짜(0-based), si: 타입(0~13)
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
        return (start_date + timedelta(days=di)).weekday()

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
            == rules.daily_D
        )
        # 중2: 평일(월~금)만 정확히 daily_M명, 주말은 0명
        중2_nurses = [ni for ni, n in enumerate(nurses) if n.role == "중2"]
        if 중2_nurses and weekday_of(di) < 5:  # 월~금 + 중2 간호사 존재 시
            model.add(
                sum(shifts[(ni, di, si)] for ni in 중2_nurses for si in M_FAMILY)
                == rules.daily_M
            )
        else:  # 주말 또는 중2 간호사 없음
            model.add(
                sum(shifts[(ni, di, si)] for ni in range(num_nurses) for si in M_FAMILY)
                == 0
            )
        model.add(
            sum(shifts[(ni, di, _E)] for ni in range(num_nurses))
            == rules.daily_E
        )
        model.add(
            sum(shifts[(ni, di, _N)] for ni in range(num_nurses))
            == rules.daily_N
        )

    # ── H2a. 중2 role 아닌 간호사는 중2 근무 금지 ──
    non_중2_nurses = [ni for ni, n in enumerate(nurses) if n.role != "중2"]
    for ni in non_중2_nurses:
        for di in range(num_days):
            for si in M_FAMILY:
                model.add(shifts[(ni, di, si)] == 0)

    # ══════════════════════════════════════════
    # 월 경계 제약 (prev_tail_shifts 기반)
    # 이전 달 마지막 근무를 분석하여 day0~day4에 추가 제약
    # ══════════════════════════════════════════
    for ni, nurse in enumerate(nurses):
        tail = nurse.prev_tail_shifts
        if not tail:
            continue
        # 빈 문자열 제거하지 않고 위치 유지 (빈칸 = 정보 없음)
        tail_len = len(tail)

        # ── 경계 H3: 역순 금지 (tail[-1] → day0) ──
        if rules.ban_reverse_order and tail_len >= 1:
            last = tail[-1]
            if last in NAME_TO_IDX:
                last_idx = NAME_TO_IDX[last]
                if last_idx in SHIFT_LEVEL:
                    for sj in WORK_INDICES:
                        if sj in SHIFT_LEVEL and SHIFT_LEVEL[last_idx] > SHIFT_LEVEL[sj]:
                            model.add(shifts[(ni, 0, sj)] == 0)

        # ── 경계 H3a: N→1off→D 금지 ──
        # tail[-2:]가 [N, OFF계열]이면 day0에 D 금지
        if tail_len >= 2:
            t2, t1 = tail[-2], tail[-1]
            if t2 == "N" and t1 in ("OFF", "주", "법휴", "수면", "생휴", "휴가", "특휴", "공가", "경가", "보수", "POFF"):
                for si in D_FAMILY:
                    model.add(shifts[(ni, 0, si)] == 0)
        # tail[-1]이 N이면 day0 OFF + day1 D 금지
        if tail_len >= 1 and tail[-1] == "N":
            model.add(
                sum(shifts[(ni, 0, oi)] for oi in ALL_OFF)
                + shifts[(ni, 1, _D)] <= 1
            ) if 1 < num_days else None

        # ── 경계 H3b: N→1off→N 금지 ──
        # tail[-2:]가 [N, OFF계열]이면 day0에 N 금지
        if tail_len >= 2:
            t2, t1 = tail[-2], tail[-1]
            if t2 == "N" and t1 in ("OFF", "주", "법휴", "수면", "생휴", "휴가", "특휴", "공가", "경가", "보수", "POFF"):
                model.add(shifts[(ni, 0, _N)] == 0)
        # tail[-1]이 N이면 day0 OFF + day1 N 금지
        if tail_len >= 1 and tail[-1] == "N" and num_days >= 2:
            model.add(
                sum(shifts[(ni, 0, oi)] for oi in ALL_OFF)
                + shifts[(ni, 1, _N)] <= 1
            )

        # ── 경계 H4: 연속 근무 ≤ max_consecutive_work ──
        # tail 끝에서 연속 근무일수 세기
        _work_set = {"D", "E", "N", "중2"}
        tail_consec_work = 0
        for s in reversed(tail):
            if s in _work_set:
                tail_consec_work += 1
            else:
                break
        # tail에서 이미 k일 연속 → day0부터 max_cw-k일 내 반드시 휴무
        if tail_consec_work > 0:
            remain = rules.max_consecutive_work - tail_consec_work
            if remain <= 0:
                # 이미 한도 도달 → day0은 반드시 휴무
                model.add(
                    sum(shifts[(ni, 0, oi)] for oi in ALL_OFF) >= 1
                )
            else:
                # remain일 이내에 휴무 1개 필요
                window = min(remain + 1, num_days)
                if window > 0:
                    model.add(
                        sum(shifts[(ni, dd, oi)]
                            for dd in range(window) for oi in ALL_OFF) >= 1
                    )

        # ── 경계 H5: 연속 N ≤ max_consecutive_N ──
        tail_consec_N = 0
        for s in reversed(tail):
            if s == "N":
                tail_consec_N += 1
            else:
                break
        if tail_consec_N > 0:
            remain_n = rules.max_consecutive_N - tail_consec_N
            if remain_n <= 0:
                model.add(shifts[(ni, 0, _N)] == 0)
            else:
                window_n = min(remain_n + 1, num_days)
                if window_n > 0:
                    model.add(
                        sum(shifts[(ni, dd, _N)]
                            for dd in range(window_n)) <= remain_n
                    )

        # ── 경계 H6: NN→2off ──
        off_after = rules.off_after_2N
        # tail[-2:]가 [N, N]이면 day0, day1 휴무
        if tail_len >= 2 and tail[-2] == "N" and tail[-1] == "N":
            for k in range(off_after):
                if k < num_days:
                    model.add(
                        sum(shifts[(ni, k, oi)] for oi in ALL_OFF) >= 1
                    )
        # tail[-1]이 N이면, day0이 N인 경우 day1,day2 휴무 필요
        elif tail_len >= 1 and tail[-1] == "N":
            for k in range(off_after):
                if 1 + k < num_days:
                    model.add(
                        shifts[(ni, 0, _N)] <= sum(shifts[(ni, 1 + k, oi)] for oi in ALL_OFF)
                    )

    # ── H3. 역순 금지 ──
    if rules.ban_reverse_order:
        for ni in range(num_nurses):
            for di in range(num_days - 1):
                for si, sj in FORBIDDEN_PAIRS:
                    model.add(
                        shifts[(ni, di, si)] + shifts[(ni, di + 1, sj)] <= 1
                    )

    # ── H3a. N→1휴무→D 금지 (N 후 D까지 최소 2일 휴무) ──
    for ni in range(num_nurses):
        for di in range(num_days - 2):
            model.add(
                shifts[(ni, di, _N)] + shifts[(ni, di + 2, _D)] <= 1
            )
    
    # ── H3b. N→1휴무→N 금지 ──
    # N, 휴무1개, N 패턴만 금지 (연속 N이나 휴무2개 이상 후 N은 허용)
    for ni in range(num_nurses):
        for di in range(num_days - 2):
            model.add(
                shifts[(ni, di, _N)]
                + sum(shifts[(ni, di + 1, oi)] for oi in ALL_OFF)
                + shifts[(ni, di + 2, _N)]
                <= 2
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
    
    # 요청 처리
    req_hard_days = set() # 요청 들어온 날짜 기록
    for r in requests:
        if not r.is_hard:
            continue
        if r.nurse_id not in nurse_idx:
            continue
        ni = nurse_idx[r.nurse_id]
        di = r.day - 1
        if di < 0 or di >= num_days:
            continue
        req_hard_days.add((ni, di))
        if r.code in NAME_TO_IDX:
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
        elif excluded == "M":  # 중간근무 추가 시
            for si in M_FAMILY:
                model.add(shifts[(ni, di, si)] == 0)
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
                else:
                    model.add(shifts[(ni, di, _주)] == 0) # 다른 날엔 주휴 안 됨

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

    # ── H11. 주당 OFF 1개 ──
    for ni in range(num_nurses):
        for w_start in range(0, num_days, 7):
            w_end = min(w_start + 7, num_days)
            off_sum = sum(shifts[(ni, di, _OFF)] for di in range(w_start, w_end))
            if w_end - w_start >= 4:  # 4일 이상 주
                model.add(off_sum == 1)
            else:
                model.add(off_sum <= 1)  # 짧은 마지막 주

    # ── H12. 책임 1명 이상 (D/E/N만, 중2 제외) ──
    chiefs = [ni for ni, n in enumerate(nurses) if n.grade == "책임"]
    if chiefs and rules.min_chief_per_shift > 0:
        for di in range(num_days):
            for si in [_D, _E, _N]:
                model.add(
                    sum(shifts[(ni, di, si)] for ni in chiefs)
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

    # ── H15. 책임만 1명 이하 (D/E/N만, 중2 제외) ──
    chief_only = [ni for ni, n in enumerate(nurses)
                  if n.role == "책임만"]
    if chief_only:
        for di in range(num_days):
            for si in [_D, _E, _N]:
                model.add(
                    sum(shifts[(ni, di, si)] for ni in chief_only) <= 1
                )

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
    obj_auto_off = []  # 추가 soft bonus (목적함수에 추가)
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

        # 생휴: 여성 월 1회 (하드 제약)
        hard_menst = hard_counts[_생휴]
        menst_sum = sum(shifts[(ni, di, _생휴)] for di in range(num_days))
        if hard_menst > 0:
            model.add(menst_sum == hard_menst)
        elif not nurse.is_male and rules.menstrual_leave:
            model.add(menst_sum == 1)
        else:
            model.add(menst_sum == 0)

        # 수면: 조건 충족 시 1개 생성 (하드 제약)
        hard_sleep = hard_counts[_수면]
        sleep_sum = sum(shifts[(ni, di, _수면)] for di in range(num_days))
        if hard_sleep > 0:
            model.add(sleep_sum == hard_sleep)
        elif nurse.pending_sleep:
            model.add(sleep_sum == 1)
        else:
            partner = get_sleep_partner_month(start_date.month)
            eff_threshold = rules.sleep_N_monthly
            if partner is not None:
                bimonthly_eff = max(0, rules.sleep_N_bimonthly - nurse.prev_month_N)
                eff_threshold = min(eff_threshold, bimonthly_eff)

            if eff_threshold <= 0:
                model.add(sleep_sum == 1)
            elif eff_threshold > rules.max_N_per_month:
                model.add(sleep_sum == 0)
            else:
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

                # 조건 충족 시 반드시 1개 (하드)
                model.add(sleep_sum == 0).only_enforce_if(sleep_needed.Not())
                model.add(sleep_sum == 1).only_enforce_if(sleep_needed)

                for di in range(num_days):
                    if di < eff_threshold:
                        model.add(shifts[(ni, di, _수면)] == 0)
                    else:
                        model.add(
                            sum(shifts[(ni, dd, _N)] for dd in range(di))
                            >= eff_threshold
                        ).only_enforce_if(shifts[(ni, di, _수면)])

        # 특휴, 공가, 경가, 보수: == hard_request_count (요청 시만)
        for idx in [_특휴, _공가, _경가, _보수]:
            model.add(
                sum(shifts[(ni, di, idx)] for di in range(num_days))
                == hard_counts[idx]
            )

        # 휴가: >= hard_request_count (나머지 여유 off 슬롯을 휴가로 채움)
        model.add(
            sum(shifts[(ni, di, _휴가)] for di in range(num_days))
            >= hard_counts[_휴가]
        )

        # 법휴: 갯수 고정 안 함 (H18 공휴일 제약이 결정)
        # POFF: H19에서 처리

    # ── H18. 공휴일 → 비근무 시 법휴만 허용 ──
    hard_req_days = set()
    for r in requests:
        if r.is_hard and r.nurse_id in nurse_idx:
            ni_r = nurse_idx[r.nurse_id]
            di_r = r.day - 1
            if 0 <= di_r < num_days:
                hard_req_days.add((ni_r, di_r))

    for di in public_holiday_dis:
        # di = hday - 1
        if di < 0 or di >= num_days:
            continue
        for ni in range(num_nurses):
            if (ni, di) in fixed_off_days:
                continue
            if (ni, di) in hard_req_days:
                continue
            for oi in ALL_OFF:
                if oi != _법휴:
                    model.add(shifts[(ni, di, oi)] == 0)

    # ── H19. 임산부 POFF: 4연속 근무 후 추가 휴무 ──
    for ni, nurse in enumerate(nurses):
        if not nurse.is_pregnant:
            for di in range(num_days):
                model.add(shifts[(ni, di, _POFF)] == 0)
            continue

        interval = rules.pregnant_poff_interval  # 4
        for di in range(num_days):
            if di < interval:
                model.add(shifts[(ni, di, _POFF)] == 0)
                continue

            if ((ni, di) in fixed_off_days
                    or (ni, di) in req_hard_days
                    or di in public_holiday_dis):
                model.add(shifts[(ni, di, _POFF)] == 0)
                continue

            work_sum = sum(
                shifts[(ni, di - k - 1, wi)]
                for k in range(interval) for wi in WORK_INDICES
            )

            # Forward: 4연속 근무 → POFF 필수
            model.add(
                shifts[(ni, di, _POFF)] >= work_sum - (interval - 1)
            )

            # Backward: POFF → 이전 4일 전부 근무
            model.add(
                work_sum >= interval * shifts[(ni, di, _POFF)]
            )

    # ── H20. 휴무 편차 제한 (±2, 주4일제 +4) ──
    # ±2: 수면/생휴 등 특수 휴무로 인한 개인차 수용
    중2_exists = any(n.role == "중2" for n in nurses)
    중2_per_weekday = rules.daily_M if 중2_exists else 0
    num_weekdays = sum(1 for di in range(num_days) if weekday_of(di) < 5)
    num_weekends = num_days - num_weekdays
    total_work_slots = (
        num_weekdays * (rules.daily_D + 중2_per_weekday + rules.daily_E + rules.daily_N)
        + num_weekends * (rules.daily_D + rules.daily_E + rules.daily_N)
    )
    total_off_slots = num_nurses * num_days - total_work_slots

    extra_off_4day = 4  # 주4일제 추가 휴무
    fourday_nis = [ni for ni in range(num_nurses) if nurses[ni].is_4day_week]
    regular_nis = [ni for ni in range(num_nurses) if not nurses[ni].is_4day_week]
    n_fourday = len(fourday_nis)

    base_off = round(
        (total_off_slots - extra_off_4day * n_fourday) / max(num_nurses, 1)
    )

    for ni in regular_nis:
        off_sum = sum(
            shifts[(ni, di, oi)]
            for di in range(num_days) for oi in ALL_OFF
        )
        model.add(off_sum >= base_off - 2)
        model.add(off_sum <= base_off + 2)

    if fourday_nis:
        fourday_target = base_off + extra_off_4day
        for ni in fourday_nis:
            off_sum = sum(
                shifts[(ni, di, oi)]
                for di in range(num_days) for oi in ALL_OFF
            )
            model.add(off_sum >= fourday_target - 2)
            model.add(off_sum <= fourday_target + 2)

    # ══════════════════════════════════════════
    # SOFT CONSTRAINTS (목적함수)
    # ══════════════════════════════════════════
    obj = list(obj_auto_off)  # 생휴/수면 soft bonus 포함

    # ── S1. 희망 요청 반영 (+100) ──
    # 공정성 페널티(-5~-8)보다 충분히 높아야 요청이 반영됨
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
            obj.append(100 * sum(shifts[(ni, di, oi)] for oi in ALL_OFF))
        elif r.code in NAME_TO_IDX:
            si = NAME_TO_IDX[r.code]
            obj.append(100 * shifts[(ni, di, si)])

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
    
    _log("solver.solve() 호출 시작...")
    status = solver.solve(model)
    
    _log(f"솔버 종료 상태: {status} (3:FEASIBLE, 4:OPTIMAL, 0:UNKNOWN)")

    # ══════════════════════════════════════════
    # 결과 추출
    # ══════════════════════════════════════════
    schedule = Schedule(
        start_date=start_date,
        nurses=nurses, rules=rules, requests=requests,
    )

    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        _log("해를 찾았습니다!")
        for ni, nurse in enumerate(nurses):
            for di in range(num_days):
                for si in range(NUM_TYPES):
                    if solver.value(shifts[(ni, di, si)]):
                        schedule.set_shift(nurse.id, di + 1, IDX_TO_NAME[si])
                        break

        # 후처리 (현재 솔버가 모든 휴무 타입을 직접 관리하므로 최소한)
        _post_process(schedule, nurses, rules)
    else:
        _log("해를 찾을 수 없습니다 (Infeasible). 인원수 설정이나 휴무 조건을 확인하세요.")
    return schedule


# ══════════════════════════════════════════
# 후처리 (최소한)
# 솔버가 법휴/POFF/수면/생휴를 직접 관리하므로
# 별도 라벨링 불필요
# ══════════════════════════════════════════

def _post_process(
    schedule: Schedule,
    nurses: list[Nurse],
    rules: Rules,
):
    """솔버 결과 후처리 (현재 솔버가 모든 휴무 타입을 직접 관리)"""
    pass
