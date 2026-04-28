"""스케줄링 엔진 - Google OR-Tools CP-SAT Solver
응급실 간호사 근무표 생성

21개 타입(D/D9/D1/중1/중2/E/N/주/OFF/법휴/수면/생휴/휴가/병가/특휴/공가/경가/보수/POFF/필수/번표)을 솔버 변수로 사용.
D9·D1·중1은 입력 전용(H8 하드요청으로만 배정, 자동배정 없음).
모든 휴무 타입을 솔버가 직접 관리하여 최적 배치.

원칙:
 - D/E/N 인원은 == (정확히 고정)
 - 나머지 인원은 자동으로 휴무 (타입도 솔버가 결정)
 - 휴무 우선순위: 주(1/주) → OFF(1/주) → 수면 → 생휴 → 나머지(휴가)

Hard Constraints:
 H1.  하루 1배정
 H2.  일일 인원 (D/E/N == 고정)
 H2a. 중2 role 아닌 간호사 → 중2 배정 불가
 H2b. D9/D1/중1 입력 전용 → 하드 요청 없으면 자동배정 불가
 H3.  역순 금지 (D→E→N)
 H3a. N→1off→D·중간·N 금지 (E만 허용) — NNN 연속은 허용
       단일 N: N→1휴무→E 가능, N→1휴무→D/중간 불가(2휴무 필요)
       NNN: N→N→N 패턴은 H3a 비적용 (di+1이 휴무일 때만 di+2 제약 발동)
 H3c. N 다음날 보수/필수/번표 금지 (실질 근무 준하는 휴무)
 H4.  최대 연속 근무 (5일)
 H5.  최대 연속 N (3개)
 H6.  N 2연속 후 휴무 2개
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
 H21. 신청 휴무 샌드위치 금지 (휴무 신청한 날이 양쪽 모두 휴무 배정이면 해당 날도 반드시 휴무)
 특수 휴무 갯수 (생휴/수면 조건부 하드, 특휴/공가/경가/보수 하드요청분, 휴가 catch-all)

Soft Constraints:
 S1. 희망 요청 반영 (A: +800+score×5, B: +250+score×5)
 S2. D/E/N 횟수 공정 (-5)
 S3. N 균등 배분 (-8)
 S4. 주말 균등 배분 (-8)
 S5. 일반 3명 이하 권고 (-3)
 S6. N 연속 배정 보상 (+20/쌍) — N 블록 유도, N 휴무 N 패턴 억제
 S7. 연속 휴무 보상 (+15/쌍) — 산발적 휴무 억제, 연속 휴무 유도
 S8. 월 N 초과 억제 (-300/개) — max_N_per_month 초과 시 강한 페널티 (소프트)
"""
from datetime import date, timedelta
from ortools.sat.python import cp_model
from engine.models import (
    Nurse, Request, Rules, Schedule, ROLE_TIERS, get_sleep_partner_month,
    WORK_SHIFTS, SHIFT_ORDER,
)
import logging as _logging
def _log(message):
    _logging.warning(f"[solver] {message}")


# ══════════════════════════════════════════
# 솔버 내 근무 타입 인덱스 (12개)
# ══════════════════════════════════════════

# 근무 (기존 인덱스 유지, 입력전용 3종은 끝에 추가)
_D, _중2, _E, _N = 0, 1, 2, 3

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
_필수 = 15
_번표 = 16
_병가 = 17

# 입력 전용 중간근무 (솔버 변수 필요, 자동배정 없음)
_D9 = 18
_D1 = 19
_중1 = 20

NUM_TYPES = 21

# 인덱스 ↔ 이름
IDX_TO_NAME = {
    _D: "D",
    _중2: "중2",
    _D9: "D9", _D1: "D1", _중1: "중1",  # 입력 전용
    _E: "E", _N: "N",
    _주: "주", _OFF: "OFF", _법휴: "법휴", _수면: "수면",
    _생휴: "생휴", _휴가: "휴가", _병가: "병가", _특휴: "특휴", _공가: "공가", _경가: "경가",
    _보수: "보수", _POFF: "POFF", _필수: "필수", _번표: "번표",
}
NAME_TO_IDX = {v: k for k, v in IDX_TO_NAME.items()}

# 휴무 그룹
REGULAR_OFF = [_주, _OFF]                                               # 주당 정규 휴무 (주1 + OFF1 = 2)
EXTRA_OFF = [_법휴, _수면, _생휴, _휴가, _병가, _특휴, _공가, _경가, _보수, _POFF, _필수, _번표]  # 추가 휴무 (주당 예산 외)
ALL_OFF = REGULAR_OFF + EXTRA_OFF                                       # 연속근무 중단 인정 대상

# 근무 패밀리 (인원 집계용)
D_FAMILY = [_D]
M_FAMILY = [_중2, _D9, _D1, _중1]  # 중간 계열 전체 (중2=솔버배정, D9/D1/중1=입력전용)
E_FAMILY = [_E]
N_FAMILY = [_N]
WORK_INDICES = [_D, _E, _N, _중2, _D9, _D1, _중1]

# 근무 순서 레벨 (역순 금지용)
SHIFT_LEVEL = {
    _D: 1,
    _중2: 2, _D9: 2, _D1: 2, _중1: 2,  # 중간 계열
    _E: 3,
    _N: 4,
}

# 역순 금지 페어 (미리 계산)
# → (N,*), (E,D/중간), (중간,D) 등 레벨 역전 쌍
FORBIDDEN_PAIRS = [
    (si, sj) for si in WORK_INDICES for sj in WORK_INDICES
    if SHIFT_LEVEL[si] > SHIFT_LEVEL[sj]
]


def validate_requests(
    nurses: list[Nurse],
    requests: list[Request],
    rules: Rules,
    start_date: date,
) -> list[str]:
    """솔버 실행 전 요청사항 사전 검증

    Returns: 경고/오류 메시지 리스트 (빈 리스트 = 문제 없음)
    """
    warnings = []
    num_days = 28
    nurse_map = {n.id: n for n in nurses}
    num_nurses = len(nurses)

    def weekday_of(di):
        return (start_date + timedelta(days=di)).weekday()

    wd_names = ["월", "화", "수", "목", "금", "토", "일"]

    # ── 인원 수 체크 ──
    중2_exists = any(n.role == "중2" for n in nurses)
    중2_per_weekday = rules.daily_M if 중2_exists else 0
    min_staff = rules.daily_D + rules.daily_E + rules.daily_N + 중2_per_weekday
    if num_nurses < min_staff:
        warnings.append(
            f"간호사 {num_nurses}명 < 일일 최소 인원 {min_staff}명 "
            f"(D{rules.daily_D}+E{rules.daily_E}+N{rules.daily_N}+중2{중2_per_weekday})"
        )

    # ── base_off 계산 (H20과 동일) ──
    num_weekdays = sum(1 for di in range(num_days) if weekday_of(di) < 5)
    num_weekends = num_days - num_weekdays
    total_work_slots = (
        num_weekdays * (rules.daily_D + 중2_per_weekday + rules.daily_E + rules.daily_N)
        + num_weekends * (rules.daily_D + rules.daily_E + rules.daily_N)
    )
    total_off_slots = num_nurses * num_days - total_work_slots
    extra_off_4day = 4
    n_fourday = sum(1 for n in nurses if n.is_4day_week)
    base_off = round(
        (total_off_slots - extra_off_4day * n_fourday) / max(num_nurses, 1)
    )

    # ── 간호사별 요청 검증 ──
    nurse_reqs = {}
    for r in requests:
        if r.nurse_id not in nurse_map:
            continue
        if r.day < 1 or r.day > num_days:
            continue
        nurse_reqs.setdefault(r.nurse_id, []).append(r)

    for nid, reqs in nurse_reqs.items():
        nurse = nurse_map[nid]
        hard_reqs = [r for r in reqs if r.is_hard]

        def fmt_day(day: int) -> str:
            """스케줄 day(1-based)를 실제 날짜 문자열로 변환"""
            dt = start_date + timedelta(days=day - 1)
            return f"{dt.month}/{dt.day}"

        # 1. 생휴: 남자 불가, 여성 월 1회 (28일 기간이 2개월에 걸치면 최대 2회)
        months_in_period = len({(start_date + timedelta(days=di)).month for di in range(num_days)})
        max_menst = months_in_period - (1 if nurse.menstrual_used else 0)
        menst_reqs = [r for r in hard_reqs if r.code == "생휴"]
        if menst_reqs:
            if nurse.is_male:
                days = ", ".join(fmt_day(r.day) for r in menst_reqs)
                warnings.append(f"{nurse.name}: 남자 간호사 생휴 불가 ({days})")
            elif len(menst_reqs) > max_menst:
                days = ", ".join(fmt_day(r.day) for r in menst_reqs)
                warnings.append(
                    f"{nurse.name}: 생휴 {len(menst_reqs)}회 신청 ({days})"
                    f" → 최대 {max_menst}회"
                )

        # 2. OFF 주당 초과 신청
        required_off_w = 2 if nurse.is_4day_week else 1
        off_reqs = [r for r in hard_reqs if r.code == "OFF"]
        off_by_week: dict[int, list] = {}
        for r in off_reqs:
            wk = (r.day - 1) // 7
            off_by_week.setdefault(wk, []).append(r)
        for wk, wreqs in off_by_week.items():
            if len(wreqs) > required_off_w:
                extra = wreqs[required_off_w:]
                days = ", ".join(fmt_day(r.day) for r in extra)
                warnings.append(
                    f"{nurse.name}: {wk+1}주차 OFF {len(wreqs)}개 신청"
                    f" → 주당 최대 {required_off_w}개, {days} 무시됨"
                )

        # 병가 스팬 계산 (이 간호사의 연속 병가 범위)
        sick_days_v = sorted(r.day for r in hard_reqs if r.code == "병가")
        sick_span_v = (sick_days_v[0], sick_days_v[-1]) if sick_days_v else None

        # 3. 주 요일 불일치
        ju_reqs = [r for r in hard_reqs if r.code == "주"]
        if ju_reqs:
            if nurse.fixed_weekly_off is None:
                days = ", ".join(fmt_day(r.day) for r in ju_reqs)
                warnings.append(
                    f"{nurse.name}: 고정 주휴 미설정 상태에서 주휴 요청 ({days})"
                )
            else:
                for r in ju_reqs:
                    wd = weekday_of(r.day - 1)
                    if wd != nurse.fixed_weekly_off:
                        warnings.append(
                            f"{nurse.name}: {fmt_day(r.day)}({wd_names[wd]}) 주휴 요청"
                            f" → 고정 주휴일은 {wd_names[nurse.fixed_weekly_off]}"
                        )

        # 3. 주당 OFF 자리 부족 검사
        # committed(비-OFF 하드 요청) + 고정주휴 → 남은 날이 required_off보다 적으면 경고
        required_off = 2 if nurse.is_4day_week else 1
        hard_req_days = {r.day for r in hard_reqs if r.code != "OFF"}
        week_num = 0
        for w_start in range(1, num_days + 1, 7):
            w_end = min(w_start + 6, num_days)
            week_len = w_end - w_start + 1
            if week_len < 4:
                continue
            week_num += 1
            # 병가 스팬으로 주 전체가 덮이면 OFF 불필요 → 경고 생략
            if sick_span_v and all(sick_span_v[0] <= d <= sick_span_v[1] for d in range(w_start, w_end + 1)):
                continue
            # 이 주에서 committed된 날 (하드 비-OFF 요청 + 고정주휴)
            committed = set()
            for d in range(w_start, w_end + 1):
                if d in hard_req_days:
                    committed.add(d)
                if (nurse.fixed_weekly_off is not None
                        and weekday_of(d - 1) == nurse.fixed_weekly_off):
                    committed.add(d)
            available = week_len - len(committed)
            effective_off = min(required_off, available)
            if effective_off < required_off:
                shortage = required_off - effective_off
                dt_start = start_date + timedelta(days=w_start - 1)
                dt_end = start_date + timedelta(days=w_end - 1)
                date_range = f"{dt_start.month}/{dt_start.day}~{dt_end.month}/{dt_end.day}"
                warnings.append(
                    f"{nurse.name}: {week_num}주차({date_range}) "
                    f"확정 휴무가 많아 OFF {shortage}개 부족 "
                    f"(가용일 {available}일, 필요 OFF {required_off}개)"
                )

        # 4. 휴가 잔여 초과
        vac_reqs = [r for r in hard_reqs if r.code == "휴가"]
        if len(vac_reqs) > nurse.vacation_days:
            warnings.append(
                f"{nurse.name}: 휴가 {len(vac_reqs)}일 신청"
                f" (잔여 {nurse.vacation_days}일)"
            )

        # 5. 하드 휴무 과다 → H20 범위 초과 (병가 있으면 자연히 초과 가능 → 생략)
        hard_off_count = len(hard_reqs)
        limit = (base_off + extra_off_4day + 2) if nurse.is_4day_week else (base_off + 2)
        if hard_off_count > limit and not sick_span_v:
            warnings.append(
                f"{nurse.name}: 확정 휴무 {hard_off_count}일"
                f" (허용 범위 최대 {limit}일)"
            )

        # 6. 같은 날 모순 (근무 요청 + 같은 근무 제외)
        day_reqs = {}
        for r in reqs:
            day_reqs.setdefault(r.day, []).append(r)
        for day, day_r_list in day_reqs.items():
            codes = [r.code for r in day_r_list]
            for shift in ["D", "E", "N"]:
                if shift in codes and f"{shift} 제외" in codes:
                    warnings.append(
                        f"{nurse.name}: {fmt_day(day)}에 {shift} 요청과"
                        f" {shift} 제외 동시 신청"
                    )

        # 7. 고정 주휴 요일에 근무 요청
        if nurse.fixed_weekly_off is not None:
            for r in reqs:
                wd = weekday_of(r.day - 1)
                if wd == nurse.fixed_weekly_off and r.code in WORK_SHIFTS:
                    warnings.append(
                        f"{nurse.name}: {fmt_day(r.day)}({wd_names[wd]})은 고정 주휴일인데"
                        f" {r.code} 근무 요청"
                    )

        # 요청된 날짜별 코드 맵 (근무+휴무 모두)
        _MID_AND_D = {"D", "D9", "D1", "중1", "중2"}
        req_day_code = {r.day: r.code for r in reqs}

        # 8. 중2 role 아닌 간호사의 중2 요청
        if nurse.role != "중2":
            bad = [r for r in reqs if r.code == "중2"]
            if bad:
                days = ", ".join(fmt_day(r.day) for r in bad)
                warnings.append(
                    f"{nurse.name}: 중2 role이 아닌데 중2 근무 요청 ({days})"
                )

        # 9. 중2 주말 요청 (중2는 평일 전용)
        for r in reqs:
            if r.code == "중2" and weekday_of(r.day - 1) >= 5:
                wd = weekday_of(r.day - 1)
                warnings.append(
                    f"{nurse.name}: {fmt_day(r.day)}({wd_names[wd]}) 중2 요청 불가"
                    f" (중2는 평일 전용)"
                )

        # 10. 역순 연속 근무 요청 (같은 간호사의 인접 요청)
        if rules.ban_reverse_order:
            for r in reqs:
                if r.code not in SHIFT_ORDER:
                    continue
                next_r_code = req_day_code.get(r.day + 1)
                if next_r_code and next_r_code in SHIFT_ORDER:
                    if SHIFT_ORDER[r.code] > SHIFT_ORDER[next_r_code]:
                        warnings.append(
                            f"{nurse.name}: 역순 요청 ({fmt_day(r.day)} {r.code}"
                            f" -> {fmt_day(r.day + 1)} {next_r_code})"
                        )

        # 11. N→1휴무→D/중간근무/N 패턴 (요청 내에서)
        _MID_AND_D_N = _MID_AND_D | {"N"}
        for r in reqs:
            if r.code == "N":
                code1 = req_day_code.get(r.day + 1, "")
                code2 = req_day_code.get(r.day + 2, "")
                if code1 and code1 not in WORK_SHIFTS and code2 in _MID_AND_D_N:
                    warnings.append(
                        f"{nurse.name}: N→휴무→{code2} 패턴 불가"
                        f" ({fmt_day(r.day)} N → {fmt_day(r.day + 1)} {code1}"
                        f" → {fmt_day(r.day + 2)} {code2})"
                    )

        # 12. 전월 tail과 이번 달 요청 간 패턴 체크
        tail = nurse.prev_tail_shifts
        if tail:
            day1_code = req_day_code.get(1, "")
            day2_code = req_day_code.get(2, "")
            # tail[-1]이 N이면 1일에 D/중간 요청 불가 (N→N 연속은 허용)
            if tail[-1] == "N" and day1_code in _MID_AND_D:
                warnings.append(
                    f"{nurse.name}: 전월 마지막 N 직후 1일 {day1_code} 요청 불가"
                )
            # tail[-2:]가 [N, 휴무]이면 1일에 D/중간/N 요청 불가
            if (len(tail) >= 2 and tail[-2] == "N"
                    and tail[-1] not in WORK_SHIFTS
                    and day1_code in _MID_AND_D_N):
                warnings.append(
                    f"{nurse.name}: 전월 N→휴무 이후 1일 {day1_code} 요청 불가"
                )
            # tail[-1]이 N이면 1일 휴무+2일 D/중간/N 패턴 불가
            if tail[-1] == "N" and day1_code and day1_code not in WORK_SHIFTS and day2_code in _MID_AND_D_N:
                warnings.append(
                    f"{nurse.name}: 전월 N → 1일 {day1_code} → 2일 {day2_code} 패턴 불가"
                )

        # 13. POFF: 임산부만 가능
        poff_reqs = [r for r in hard_reqs if r.code == "POFF"]
        if poff_reqs and not nurse.is_pregnant:
            days = ", ".join(fmt_day(r.day) for r in poff_reqs)
            warnings.append(f"{nurse.name}: POFF는 임산부만 신청 가능 ({days})")

        # 14. 법휴: 공휴일에만
        holiday_set = set(rules.public_holidays)
        for r in hard_reqs:
            if r.code == "법휴" and r.day not in holiday_set:
                warnings.append(
                    f"{nurse.name}: {fmt_day(r.day)}은 공휴일이 아닌데 법휴 요청"
                )

        # 15. N 다음날 보수/필수/번표 금지 (H3c)
        _near_work = {"보수", "필수", "번표"}
        for r in reqs:
            if r.code == "N":
                nxt = req_day_code.get(r.day + 1, "")
                if nxt in _near_work:
                    warnings.append(
                        f"{nurse.name}: N 다음날 {nxt} 요청 불가"
                        f" ({fmt_day(r.day)} N → {fmt_day(r.day + 1)} {nxt})"
                    )

        # 16. NN 후 2일 휴무 체크
        for r in reqs:
            if r.code == "N" and req_day_code.get(r.day - 1) == "N":
                nxt1 = req_day_code.get(r.day + 1, "")
                nxt2 = req_day_code.get(r.day + 2, "")
                if nxt1 in WORK_SHIFTS:
                    warnings.append(
                        f"{nurse.name}: NN 후 2일 휴무 필요"
                        f" — {fmt_day(r.day + 1)} {nxt1} 요청 불가"
                    )
                elif nxt1 and nxt1 not in WORK_SHIFTS and nxt2 in WORK_SHIFTS:
                    warnings.append(
                        f"{nurse.name}: NN 후 2일 휴무 필요"
                        f" — {fmt_day(r.day + 2)} {nxt2} 요청 불가"
                    )

        # 17. 월 N 최대 초과
        n_count = sum(1 for r in reqs if r.code == "N")
        if n_count > rules.max_N_per_month:
            warnings.append(
                f"{nurse.name}: N 요청 {n_count}개 — 월 최대 {rules.max_N_per_month}개 초과"
            )

        # 18. 연속 N 초과
        max_cn = rules.max_consecutive_N
        tail = nurse.prev_tail_shifts
        reported = False
        for r in reqs:
            if reported:
                break
            if r.code != "N":
                continue
            count = 1
            d2 = r.day - 1
            while d2 >= 1 and req_day_code.get(d2) == "N":
                count += 1
                d2 -= 1
            if d2 == 0 and tail:
                for t in reversed(tail):
                    if t == "N":
                        count += 1
                    else:
                        break
            d2 = r.day + 1
            while d2 <= num_days and req_day_code.get(d2) == "N":
                count += 1
                d2 += 1
            if count > max_cn:
                warnings.append(
                    f"{nurse.name}: 연속 N {count}개 요청 — 최대 {max_cn}개 초과"
                    f" ({fmt_day(r.day)} 기준)"
                )
                reported = True

        # 19. 연속 근무 초과
        max_w = rules.max_consecutive_work
        reported = False
        for r in reqs:
            if reported:
                break
            if r.code not in WORK_SHIFTS:
                continue
            count = 1
            d2 = r.day - 1
            while d2 >= 1 and req_day_code.get(d2) in WORK_SHIFTS:
                count += 1
                d2 -= 1
            if d2 == 0 and tail:
                for t in reversed(tail):
                    if t in WORK_SHIFTS:
                        count += 1
                    else:
                        break
            d2 = r.day + 1
            while d2 <= num_days and req_day_code.get(d2) in WORK_SHIFTS:
                count += 1
                d2 += 1
            if count > max_w:
                warnings.append(
                    f"{nurse.name}: 연속 근무 {count}일 요청 — 최대 {max_w}일 초과"
                    f" ({fmt_day(r.day)} 기준)"
                )
                reported = True

    return warnings


def _diagnose_infeasible(nurses, requests, rules, start_date, num_days, shifts, full_model, checkpoints: dict):
    """INFEASIBLE 원인 제약 그룹 진단.

    checkpoints: {"그룹명": 제약인덱스} — solve_schedule에서 각 H* 그룹 직후 기록
    """
    from ortools.sat.python import cp_model as _cp

    base_proto = full_model.proto
    total = len(base_proto.constraints)
    num_nurses = len(nurses)

    _log(f"[진단] 총 제약 {total}개 | 그룹 체크포인트: {list(checkpoints.keys())}")

    # ── 사전 분석 (solver 없이) ──
    chiefs = [n for n in nurses if n.grade == "책임"]
    seniors = [n for n in nurses if n.grade in ("책임", "서브차지")]
    _log(f"[진단] 간호사 구성: 총 {num_nurses}명 | 책임 {len(chiefs)}명 | 책임+서브차지 {len(seniors)}명")
    _log(f"[진단] 규칙: daily_N={rules.daily_N} maxN={rules.max_N_per_month} "
         f"min_chief={rules.min_chief_per_shift} min_senior={rules.min_senior_per_shift}")
    # H12 분석: 책임만으로 N 커버 가능한지
    if chiefs and rules.min_chief_per_shift > 0:
        need_chief_n = rules.min_chief_per_shift * num_days
        cap_chief_n  = len(chiefs) * rules.max_N_per_month
        _log(f"[진단] H12 책임N 필요량={need_chief_n} vs 용량={cap_chief_n} "
             f"({'OK' if cap_chief_n >= need_chief_n else '★부족!'})")
    # H13 분석: 책임+서브차지로 N 커버 가능한지
    if seniors and rules.min_senior_per_shift > 0:
        need_senior_n = rules.min_senior_per_shift * num_days
        cap_senior_n  = len(seniors) * rules.max_N_per_month
        _log(f"[진단] H13 시니어N 필요량={need_senior_n} vs 용량={cap_senior_n} "
             f"({'OK' if cap_senior_n >= need_senior_n else '★부족!'})")
    # H14 분석: ROLE_TIERS 마지막 티어 N 상한
    from engine.models import ROLE_TIERS
    for tier_roles, max_d, max_e, max_n in ROLE_TIERS:
        tier_nurses = [n for n in nurses if n.role in tier_roles]
        if tier_nurses:
            non_tier = num_nurses - len(tier_nurses)
            # 이 그룹 N 상한 + 나머지 전원 N 가능 인원으로 daily_N 충족 여부
            max_daily_n = min(max_n, len(tier_nurses)) + non_tier
            _log(f"[진단] H14 역할티어 {sorted(tier_roles)} → N 상한/일={max_n} | "
                 f"해당 간호사={len(tier_nurses)}명 | 비해당={non_tier}명 | "
                 f"이론최대N={max_daily_n} "
                 f"{'OK' if max_daily_n >= rules.daily_N else f'★ 절대 부족! (최대{max_daily_n}<필요{rules.daily_N})'}")

    def test_up_to(n: int) -> str:
        """'OK' | 'INFEASIBLE' | 'TIMEOUT' 반환"""
        m = _cp.CpModel()
        m.proto.variables.extend(base_proto.variables)
        m.proto.constraints.extend(
            base_proto.constraints[i] for i in range(n)
        )
        s = _cp.CpSolver()
        s.parameters.max_time_in_seconds = 15
        s.parameters.num_workers = 2
        status = s.solve(m)
        if status in (_cp.OPTIMAL, _cp.FEASIBLE):
            return "OK"
        elif status == _cp.INFEASIBLE:
            return "INFEASIBLE"
        else:
            return "TIMEOUT"

    # 그룹별로 순서대로 테스트
    prev_name = "(기본 변수)"
    prev_idx = 0
    for name, idx in sorted(checkpoints.items(), key=lambda x: x[1]):
        result = test_up_to(idx)
        _log(f"[진단]   {prev_name}~{name} (제약 {prev_idx}→{idx}): {result}")
        if result == "INFEASIBLE":
            _log(f"[진단] ★ 원인 그룹: [{name}] 제약 추가 시 INFEASIBLE 발생 ({prev_idx}~{idx}번 제약)")
            return
        elif result == "TIMEOUT":
            _log(f"[진단]   → TIMEOUT — 더 긴 시간이 필요하거나 다음 그룹에서 진단 계속")
        prev_name = name
        prev_idx = idx

    # 체크포인트 이후 나머지
    if prev_idx < total:
        result = test_up_to(total)
        _log(f"[진단]   {prev_name}~끝 (제약 {prev_idx}→{total}): {result}")
        if result == "INFEASIBLE":
            _log(f"[진단] ★ 원인 그룹: 마지막 그룹 ({prev_idx}~{total}번 제약)")
        elif result == "TIMEOUT":
            _log("[진단] 마지막 그룹 TIMEOUT — 시간 부족으로 진단 불가")
    else:
        _log("[진단] 모든 그룹 OK — 조합 충돌일 수 있음")


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

    # 진단용 체크포인트: 각 H* 그룹 추가 후 제약 수 기록
    _cp_idx: dict[str, int] = {}

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
    _cp_idx["H1(1개배정)"] = len(model.proto.constraints)

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

    _cp_idx["H2(일일인원)"] = len(model.proto.constraints)
    # ── H2a. 중2 role 아닌 간호사는 중2 근무 금지 (D9/D1/중1은 별도 처리) ──
    non_중2_nurses = [ni for ni, n in enumerate(nurses) if n.role != "중2"]
    for ni in non_중2_nurses:
        for di in range(num_days):
            model.add(shifts[(ni, di, _중2)] == 0)

    # ── H2b. D9/D1/중1 입력 전용: 신청(hard/soft 무관)이 없으면 자동배정 불가 ──
    # D9/D1/중1은 신청 없이 배정이 불가능한 구조이므로 condition 무관하게 허용
    _input_only_allowed: dict[int, set] = {_D9: set(), _D1: set(), _중1: set()}
    for r in requests:
        if r.code in ("D9", "D1", "중1") and not r.is_or and r.nurse_id in nurse_idx:
            ni = nurse_idx[r.nurse_id]
            di = r.day - 1
            if 0 <= di < num_days and r.code in NAME_TO_IDX:
                _input_only_allowed[NAME_TO_IDX[r.code]].add((ni, di))
    for si in (_D9, _D1, _중1):
        for ni in range(num_nurses):
            for di in range(num_days):
                if (ni, di) not in _input_only_allowed[si]:
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

        # ── 경계 H3a: N→1off→(D/중간근무/N) 금지 ──
        # tail[-2:]가 [N, OFF계열]이면 day0에 D/중간/N 금지
        if tail_len >= 2:
            t2, t1 = tail[-2], tail[-1]
            if t2 == "N" and t1 in ("OFF", "주", "법휴", "수면", "생휴", "휴가", "병가", "특휴", "공가", "경가", "보수", "POFF", "필수", "번표"):
                for si in D_FAMILY + M_FAMILY + [_N]:
                    model.add(shifts[(ni, 0, si)] == 0)
        # tail[-1]이 N이면 day0 OFF + day1 D/중간/N 금지
        if tail_len >= 1 and tail[-1] == "N" and num_days >= 2:
            for si in D_FAMILY + M_FAMILY + [_N]:
                model.add(
                    sum(shifts[(ni, 0, oi)] for oi in ALL_OFF)
                    + shifts[(ni, 1, si)] <= 1
                )

        # ── 경계 H3c: N 다음날 보수/필수/번표 금지 ──
        if tail_len >= 1 and tail[-1] == "N":
            for si in (_보수, _필수, _번표):
                model.add(shifts[(ni, 0, si)] == 0)

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

    _cp_idx["H2a-H2b(중2/입력전용)"] = len(model.proto.constraints)
    # ── H3. 역순 금지 ──
    if rules.ban_reverse_order:
        for ni in range(num_nurses):
            for di in range(num_days - 1):
                for si, sj in FORBIDDEN_PAIRS:
                    model.add(
                        shifts[(ni, di, si)] + shifts[(ni, di + 1, sj)] <= 1
                    )

    # ── H3a. N→1휴무→(D/중간근무/N) 금지 ──
    # N 후 1휴무 뒤에는 E만 허용, D·D9·D1·중1·중2·N 불가
    # 단, N→N→N(NNN 연속) 패턴은 허용 — di+1이 OFF일 때만 di+2 제약 적용
    # CP-SAT 표현: N[di] + off[di+1] + D/M/N[di+2] <= 2
    #   off[di+1]=1 → N[di+2]≤0 (금지)
    #   off[di+1]=0 (= di+1이 N) → 제약 비활성화 (NNN 허용)
    for ni in range(num_nurses):
        for di in range(num_days - 2):
            off_next = sum(shifts[(ni, di + 1, oi)] for oi in ALL_OFF)
            for si in D_FAMILY + M_FAMILY + [_N]:
                model.add(
                    shifts[(ni, di, _N)] + off_next + shifts[(ni, di + 2, si)] <= 2
                )


    # ── H3c. N 다음날 보수/필수/번표 금지 ──
    # 보수(교육), 필수, 번표는 실질 근무에 준하므로 N 직후 배치 불가
    for ni in range(num_nurses):
        for di in range(num_days - 1):
            for si in (_보수, _필수, _번표):
                model.add(
                    shifts[(ni, di, _N)] + shifts[(ni, di + 1, si)] <= 1
                )

    _cp_idx["H3(역순금지)"] = len(model.proto.constraints)
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

    _cp_idx["H4-H5(연속근무/연속N)"] = len(model.proto.constraints)
    # ── H6. N 2연속 이상(NN/NNN) 블록 종료 후 휴무 ──
    # 핵심: 블록 중간이 아닌 블록 끝(di)에서만 off_after 강제
    # 조건: N[di] AND N[di-1] AND NOT N[di+1] → off at di+1..di+off_after
    # CP-SAT 표현: N[di] + N[di-1] - N[di+1] - 1 <= ALL_OFF[di+1+k]
    # → N[di+1]=1이면 좌변≤0 → 제약 비활성화(블록 계속 이어짐)
    # → N[di+1]=0이면 좌변=1 → 휴무 강제(블록 종료)
    off_after = rules.off_after_2N
    for ni in range(num_nurses):
        for di in range(1, num_days):          # di >= 1: 이전 날(di-1) 존재
            next_di = di + 1
            n_next = shifts[(ni, next_di, _N)] if next_di < num_days else 0
            for k in range(off_after):
                target = di + 1 + k
                if target < num_days:
                    model.add(
                        shifts[(ni, di, _N)] + shifts[(ni, di - 1, _N)]
                        - n_next - 1
                        <= sum(shifts[(ni, target, oi)] for oi in ALL_OFF)
                    )

    _cp_idx["H6(NN후휴무)"] = len(model.proto.constraints)

    # ── [진단용] N 가용 인원 분석 ──
    # 경계 H6으로 인해 강제 휴무인 날 계산
    _n_blocked_days: dict[int, set[int]] = {ni: set() for ni in range(num_nurses)}
    for ni, nurse in enumerate(nurses):
        tail = nurse.prev_tail_shifts
        if not tail:
            continue
        tail_len = len(tail)
        if tail_len >= 2 and tail[-2] == "N" and tail[-1] == "N":
            for k in range(rules.off_after_2N):
                if k < num_days:
                    _n_blocked_days[ni].add(k)
    _total_n_capacity = sum(
        rules.max_N_per_month - len(_n_blocked_days[ni])
        for ni in range(num_nurses)
    )
    _total_n_needed = rules.daily_N * num_days
    _n_tail_blocked = sum(len(v) for v in _n_blocked_days.values())
    _log(f"[진단] N 가용 분석: 필요={_total_n_needed} | "
         f"maxN합계={num_nurses*rules.max_N_per_month} | "
         f"경계NN 강제휴무합={_n_tail_blocked}일 | "
         f"실질 N 용량={_total_n_capacity}")
    # 날짜별로 N 가능 간호사 수 확인 (경계제약 기준)
    _day_n_avail = []
    for di in range(num_days):
        avail = sum(1 for ni in range(num_nurses) if di not in _n_blocked_days[ni])
        _day_n_avail.append(avail)
    _min_avail = min(_day_n_avail)
    _min_days = [di+1 for di, a in enumerate(_day_n_avail) if a == _min_avail]
    _log(f"[진단] 날짜별 N 최소 가용 인원: {_min_avail}명 (day {_min_days[:5]}...)")
    if _min_avail < rules.daily_N:
        _log(f"[진단] ★ 경계조건으로 day {_min_days[:3]}에 N 가용인원({_min_avail})이 "
             f"daily_N({rules.daily_N})보다 부족!")

    # ── 병가 기간 계산 ──
    # 병가 신청 첫날~마지막날 사이는 전부 병가로 처리
    # (주휴·OFF 등 다른 휴무 없이 병가로만 채움)
    nurse_병가_span: dict[int, tuple[int, int] | None] = {}
    for ni, nurse in enumerate(nurses):
        sick_days = sorted(
            r.day - 1 for r in requests
            if r.nurse_id == nurse.id and r.is_hard and r.code == "병가"
            and 0 <= r.day - 1 < num_days
        )
        nurse_병가_span[ni] = (sick_days[0], sick_days[-1]) if sick_days else None

    def in_병가_span(ni: int, di: int) -> bool:
        span = nurse_병가_span[ni]
        return span is not None and span[0] <= di <= span[1]

    # ── 공휴일 날짜 인덱스 사전 계산 (H8 필터링에서도 사용) ──
    # rules.public_holidays는 스케줄 위치(1-28) → 0-indexed di로 변환
    _holiday_days = set(rules.public_holidays)
    public_holiday_dis = {h - 1 for h in _holiday_days if 1 <= h <= num_days}

    _cp_idx["H6(NN후휴무)"] = len(model.proto.constraints)
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
    menst_hard_used = {}  # nurse_id → 생휴 하드 처리 횟수
    off_week_used = {}    # (ni, week_idx) → OFF 하드 처리 횟수 (주당 required_off개 한도)
    for r in requests:
        if not r.is_hard:
            continue
        if r.nurse_id not in nurse_idx:
            continue
        ni = nurse_idx[r.nurse_id]
        di = r.day - 1
        if di < 0 or di >= num_days:
            continue
        # 생휴: 남자 불가, 여성은 월별 최대치까지 하드 처리
        if r.code == "생휴":
            if nurses[ni].is_male:
                continue
            nurse_obj = nurses[ni]
            _months = len({(start_date + timedelta(days=d)).month for d in range(num_days)})
            _max_menst = _months - (1 if nurse_obj.menstrual_used else 0)
            menst_hard_used.setdefault(r.nurse_id, 0)
            if menst_hard_used[r.nurse_id] >= _max_menst:
                continue  # 최대치 초과 → 무시
            menst_hard_used[r.nurse_id] += 1
        # 병가 기간 중 주 요청은 무시 (병가 기간은 병가로만 채움)
        if r.code == "주" and in_병가_span(ni, di):
            continue
        # 주: 고정주휴 미설정이거나 잘못된 요일이면 무시 (H10/H10a와 충돌 방지)
        if r.code == "주":
            if nurses[ni].fixed_weekly_off is None:
                continue
            if weekday_of(di) != nurses[ni].fixed_weekly_off:
                continue
        # 법휴: 공휴일이 아닌 날이면 무시 (H10b와 충돌 방지)
        if r.code == "법휴" and di not in public_holiday_dis:
            continue
        # OFF: 주당 required_off개 초과 신청 시 무시 (H11과 충돌 방지)
        if r.code == "OFF":
            required = 2 if nurses[ni].is_4day_week else 1
            week_idx = di // 7
            key = (ni, week_idx)
            off_week_used.setdefault(key, 0)
            if off_week_used[key] >= required:
                continue
            off_week_used[key] += 1
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

    _cp_idx["H8-H9(확정요청/제외)"] = len(model.proto.constraints)
    # ── H10. 고정 주휴 ──
    for ni, nurse in enumerate(nurses):
        if nurse.fixed_weekly_off is not None:
            for di in range(num_days):
                if weekday_of(di) == nurse.fixed_weekly_off:
                    if in_병가_span(ni, di):
                        # 병가 기간 중 고정 주휴일 → 주 대신 병가로 강제
                        model.add(shifts[(ni, di, _주)] == 0)
                        model.add(shifts[(ni, di, _병가)] == 1)
                    else:
                        model.add(shifts[(ni, di, _주)] == 1)
                else:
                    model.add(shifts[(ni, di, _주)] == 0) # 다른 날엔 주휴 안 됨

    # ── H10a. 주는 고정 주휴일에만 배치 가능 ──
    for ni, nurse in enumerate(nurses):
        for di in range(num_days):
            if nurse.fixed_weekly_off is None or weekday_of(di) != nurse.fixed_weekly_off:
                model.add(shifts[(ni, di, _주)] == 0)

    # ── H10b. 법휴는 공휴일에만 배치 가능 ──
    for ni in range(num_nurses):
        for di in range(num_days):
            if di not in public_holiday_dis:
                model.add(shifts[(ni, di, _법휴)] == 0)

    # ── 주당 OFF 배치 가능일 사전 계산 ──
    # 하드 커밋(비-OFF 타입) + 고정주휴일은 OFF 불가
    nurse_committed_days: dict[int, set[int]] = {ni: set() for ni in range(num_nurses)}
    for r in requests:
        if not r.is_hard or r.nurse_id not in nurse_idx:
            continue
        ni_r = nurse_idx[r.nurse_id]
        di_r = r.day - 1
        if 0 <= di_r < num_days and r.code in NAME_TO_IDX and r.code != "OFF":
            nurse_committed_days[ni_r].add(di_r)
    for ni, nurse in enumerate(nurses):
        if nurse.fixed_weekly_off is not None:
            for di in range(num_days):
                if weekday_of(di) == nurse.fixed_weekly_off:
                    nurse_committed_days[ni].add(di)

    _cp_idx["H10(고정주휴)"] = len(model.proto.constraints)
    # ── H11. 주당 OFF ≥ N개 (일반 1개, 주4일제 2개) — 법휴 대체 허용 ──
    # 공휴일 주에 법휴를 받으면 해당 법휴가 OFF 요구를 대체할 수 있음
    # (_OFF + 법휴) >= required, _OFF <= required (OFF 자체는 초과 불가)
    for ni in range(num_nurses):
        required_off = 2 if nurses[ni].is_4day_week else 1
        committed = nurse_committed_days[ni]
        for w_start in range(0, num_days, 7):
            w_end = min(w_start + 7, num_days)
            off_sum = sum(shifts[(ni, di, _OFF)] for di in range(w_start, w_end))
            if w_end - w_start < 4:
                model.add(off_sum <= required_off)  # 짧은 마지막 주
                continue
            available = sum(1 for di in range(w_start, w_end) if di not in committed)
            effective_off = min(required_off, available)
            # 법휴가 있는 주는 법휴로 OFF 요구 대체 가능
            hol_sum = sum(
                shifts[(ni, di, _법휴)]
                for di in range(w_start, w_end)
                if di in public_holiday_dis
            )
            model.add(off_sum + hol_sum >= effective_off)
            model.add(off_sum <= effective_off)

    _cp_idx["H11(주당OFF)"] = len(model.proto.constraints)
    # ── [진단] H11 후 간호사별 OFF 현황 ──
    _off_totals = {}
    for ni, nurse in enumerate(nurses):
        required_off = 2 if nurse.is_4day_week else 1
        _off_total = required_off * 4  # 4주
        _off_totals[ni] = _off_total
    _주_count = sum(1 for ni, nurse in enumerate(nurses) if nurse.fixed_weekly_off is not None) * 4
    _log(f"[진단] H11후: 고정주휴 설정 간호사={sum(1 for n in nurses if n.fixed_weekly_off is not None)}명 "
         f"| 月 총 주 수={_주_count} OFF 수={sum(_off_totals.values())} 생휴예상={sum(1 for n in nurses if not n.is_male)}")
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

    _cp_idx["H12(책임등급)"] = len(model.proto.constraints)
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

    _cp_idx["H14(역할티어)"] = len(model.proto.constraints)
    # ── H15. 책임만 1명 이하 (D/E/N만, 중2 제외) ──
    chief_only = [ni for ni, n in enumerate(nurses)
                  if n.role == "책임만"]
    if chief_only:
        for di in range(num_days):
            for si in [_D, _E, _N]:
                model.add(
                    sum(shifts[(ni, di, si)] for ni in chief_only) <= 1
                )

    _cp_idx["H15(책임만상한)"] = len(model.proto.constraints)
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

    _cp_idx["H17(임산부연속)"] = len(model.proto.constraints)
    # ══════════════════════════════════════════
    # 특수 휴무 갯수 제약 (타입별 정확한 수 강제)
    # ══════════════════════════════════════════
    from collections import Counter as _Counter
    _month_day_counts = _Counter(
        (start_date + timedelta(days=di)).month for di in range(num_days)
    )
    _period_months = len(_month_day_counts)
    _log(f"[생휴] 기간 내 달별 일수: {dict(_month_day_counts)} | 달 수={_period_months} | menstrual_used 현황: "
         f"{sum(1 for n in nurses if n.menstrual_used)}명 True / {sum(1 for n in nurses if not n.is_male and not n.menstrual_used)}명 False(여성)")

    obj_auto_off = []  # 추가 soft bonus (목적함수에 추가)
    for ni, nurse in enumerate(nurses):
        # 각 특수 off 타입별 하드 요청 갯수 계산
        hard_counts = {}
        for code, idx in [("생휴", _생휴), ("수면", _수면), ("휴가", _휴가), ("병가", _병가),
                          ("특휴", _특휴), ("공가", _공가), ("경가", _경가),
                          ("보수", _보수), ("필수", _필수), ("번표", _번표)]:
            hard_counts[idx] = sum(
                1 for r in requests
                if r.is_hard and r.nurse_id == nurse.id
                and r.code == code
                and 1 <= r.day <= num_days
                and (ni, r.day - 1) not in fixed_off_days
            )

        # 병가 span 내 고정 주휴일 → 주 대신 병가로 강제되므로 카운트에 추가
        span = nurse_병가_span[ni]
        if span is not None:
            span_s, span_e = span
            hard_counts[_병가] += sum(
                1 for di in range(num_days)
                if (ni, di) in fixed_off_days and span_s <= di <= span_e
            )

        # 생휴: 여성 월 1회 (하드 제약), 남자 0
        # _period_months: 기간 내 달 수, menstrual_used: 이전 근무표에서 시작 달 생휴 사용 여부
        max_menst = max(0, _period_months - (1 if nurse.menstrual_used else 0))
        menst_sum = sum(shifts[(ni, di, _생휴)] for di in range(num_days))
        if nurse.is_male:
            model.add(menst_sum == 0)
        elif hard_counts[_생휴] > 0:
            model.add(menst_sum == min(hard_counts[_생휴], max_menst))
        elif rules.menstrual_leave and max_menst > 0:
            model.add(menst_sum == max_menst)
        else:
            model.add(menst_sum == 0)

        # 생휴: 달마다 최대 1회 (같은 달 두 개 방지)
        if not nurse.is_male:
            for _month, _month_cnt in _month_day_counts.items():
                _month_days = [di for di in range(num_days)
                               if (start_date + timedelta(days=di)).month == _month]
                _month_menst = sum(shifts[(ni, di, _생휴)] for di in _month_days)
                _is_start_month = _month == start_date.month
                if nurse.menstrual_used and _is_start_month:
                    model.add(_month_menst == 0)
                else:
                    model.add(_month_menst <= 1)

    _cp_idx["특수OFF-생휴"] = len(model.proto.constraints)
    for ni, nurse in enumerate(nurses):
        # 수면: 조건 충족 시 1개 생성 (하드 제약)
        hard_counts = {}
        for code, idx in [("생휴", _생휴), ("수면", _수면), ("휴가", _휴가), ("병가", _병가),
                          ("특휴", _특휴), ("공가", _공가), ("경가", _경가),
                          ("보수", _보수), ("필수", _필수), ("번표", _번표)]:
            hard_counts[idx] = sum(
                1 for r in requests
                if r.is_hard and r.nurse_id == nurse.id
                and r.code == code
                and 1 <= r.day <= num_days
                and (ni, r.day - 1) not in fixed_off_days
            )
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

                # eff_threshold일 이전엔 수면 불가 (최소한 그 날수가 지나야 N 누적 가능)
                # 누적 N 체크는 제거: per-day 조건부 690개 제약이 솔버 성능을 급격히 저하시킴
                for di in range(min(eff_threshold, num_days)):
                    model.add(shifts[(ni, di, _수면)] == 0)

    _cp_idx["특수OFF-수면"] = len(model.proto.constraints)
    _log(f"[진단] 총 제약 수: {len(model.proto.constraints)}개 | 변수: {num_nurses}×28×{NUM_TYPES}={num_nurses*28*NUM_TYPES}개")

    # 진단: 특수OFF 하드 요청 현황 출력
    _special_off_codes = [("생휴", _생휴), ("수면", _수면), ("휴가", _휴가), ("병가", _병가),
                          ("특휴", _특휴), ("공가", _공가), ("경가", _경가),
                          ("보수", _보수), ("필수", _필수), ("번표", _번표)]
    for ni, nurse in enumerate(nurses):
        nurse_hard = {}
        for code, idx in _special_off_codes:
            cnt = sum(
                1 for r in requests
                if r.is_hard and r.nurse_id == nurse.id
                and r.code == code
                and 1 <= r.day <= num_days
                and (ni, r.day - 1) not in fixed_off_days
            )
            if cnt > 0:
                nurse_hard[code] = cnt
        if nurse_hard:
            _log(f"[특수OFF 하드요청] {nurse.name}: {nurse_hard}")

    for ni, nurse in enumerate(nurses):
        hard_counts = {}
        for code, idx in _special_off_codes:
            hard_counts[idx] = sum(
                1 for r in requests
                if r.is_hard and r.nurse_id == nurse.id
                and r.code == code
                and 1 <= r.day <= num_days
                and (ni, r.day - 1) not in fixed_off_days
            )
        # 병가 span 내 고정 주휴일은 H10a에서 병가로 강제됨 → 카운트에 추가
        span = nurse_병가_span[ni]
        if span is not None:
            span_s, span_e = span
            hard_counts[_병가] += sum(
                1 for di in range(num_days)
                if (ni, di) in fixed_off_days and span_s <= di <= span_e
            )
        # 번표, 병가: hard → 월 총 배정 수 정확히 == 요청 수
        for idx in [_번표, _병가]:
            model.add(
                sum(shifts[(ni, di, idx)] for di in range(num_days))
                == hard_counts[idx]
            )
        # 특휴, 공가, 경가, 보수, 필수: soft → 신청하지 않은 날에는 배정 불가
        # (신청한 날에는 S1 가중치로 반영 시도, 인원 부족 시 미반영 가능)
        _soft_specific = [("특휴", _특휴), ("공가", _공가), ("경가", _경가), ("보수", _보수), ("필수", _필수)]
        _soft_req_days = {idx: set() for _, idx in _soft_specific}
        for r in requests:
            if r.nurse_id == nurse.id and r.code in {c for c, _ in _soft_specific}:
                di_r = r.day - 1
                if 0 <= di_r < num_days:
                    _soft_req_days[NAME_TO_IDX[r.code]].add(di_r)
        for _, idx in _soft_specific:
            for di in range(num_days):
                if di not in _soft_req_days[idx]:
                    model.add(shifts[(ni, di, idx)] == 0)

    _cp_idx["특수OFF-기타(==)"] = len(model.proto.constraints)
    for ni, nurse in enumerate(nurses):
        hard_counts = {}
        for code, idx in _special_off_codes:
            hard_counts[idx] = sum(
                1 for r in requests
                if r.is_hard and r.nurse_id == nurse.id
                and r.code == code
                and 1 <= r.day <= num_days
                and (ni, r.day - 1) not in fixed_off_days
            )
        # 병가 span 내 고정 주휴일 카운트 추가 (위와 동일)
        span = nurse_병가_span[ni]
        if span is not None:
            span_s, span_e = span
            hard_counts[_병가] += sum(
                1 for di in range(num_days)
                if (ni, di) in fixed_off_days and span_s <= di <= span_e
            )

        # 휴가: >= hard_request_count (나머지 여유 off 슬롯을 휴가로 채움)
        model.add(
            sum(shifts[(ni, di, _휴가)] for di in range(num_days))
            >= hard_counts[_휴가]
        )

        # 법휴: 갯수 고정 안 함 (H18 공휴일 제약이 결정)
        # POFF: H19에서 처리

    _cp_idx["H12-H17(등급/역할/임산부)"] = len(model.proto.constraints)
    # ── H18. 공휴일 → 비근무 시 법휴만 허용 ──
    hard_req_days = set()
    for r in requests:
        if r.is_hard and r.nurse_id in nurse_idx:
            ni_r = nurse_idx[r.nurse_id]
            di_r = r.day - 1
            if 0 <= di_r < num_days:
                hard_req_days.add((ni_r, di_r))

    # H18: 공휴일에 비근무 시 법휴만 허용 (주휴/하드요청 제외)
    # _OFF는 차단 — 공휴일에는 법휴여야 함. H11은 법휴로 대체 가능하도록 별도 수정
    h18_count = 0
    for di in public_holiday_dis:
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
                    h18_count += 1
    _log(f"[H18] {h18_count}개 제약 추가 (공휴일={public_holiday_dis})")

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

    _cp_idx["H18-H19(공휴일/임산부POFF)"] = len(model.proto.constraints)
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

    extra_off_4day = 5  # 주4일제 추가 휴무 (주당 OFF 2개 = 일반 대비 5일 추가)
    fourday_nis = [ni for ni in range(num_nurses) if nurses[ni].is_4day_week]
    regular_nis = [ni for ni in range(num_nurses) if not nurses[ni].is_4day_week]
    n_fourday = len(fourday_nis)

    base_off = round(
        (total_off_slots - extra_off_4day * n_fourday) / max(num_nurses, 1)
    )

    # 하드 휴무 + H11 최소 OFF + 자동배정 OFF 합계가 범위 초과 시 H20 제외
    # 생휴(여성 자동), 수면(auto/pending), 법휴(공휴일 강제)를 모두 포함해야
    # "우영미(번표)+생휴+수면+법휴=14 > 13" 같은 경우를 정확히 건너뜀
    def _expected_off_count(ni):
        nid = nurses[ni].id
        hard_off = sum(
            1 for r in requests
            if r.nurse_id == nid and r.is_hard
            and 1 <= r.day <= num_days
        )
        # H10 FWO 주 일수 추가 — 주휴일은 ALL_OFF에 포함되므로 반드시 계산
        span = nurse_병가_span[ni]
        nurse_fwo = nurses[ni].fixed_weekly_off
        if nurse_fwo is not None:
            for di in range(num_days):
                if weekday_of(di) == nurse_fwo:
                    if not (span and span[0] <= di <= span[1]):
                        hard_off += 1
        # H11 mandated OFFs per week
        required = 2 if nurses[ni].is_4day_week else 1
        for w in range(0, num_days, 7):
            w_end = min(w + 7, num_days)
            if w_end - w < 4:
                continue
            if span and all(span[0] <= di <= span[1] for di in range(w, w_end)):
                continue
            if span and any(span[0] <= di <= span[1] for di in range(w, w_end)):
                avail = sum(
                    1 for di in range(w, w_end)
                    if not (span[0] <= di <= span[1])
                    and not (nurse_fwo is not None and weekday_of(di) == nurse_fwo)
                )
                hard_off += min(required, avail)
            else:
                hard_off += required

        # ── 자동 배정 OFF 추정 (H20 skip 여부 판단용) ──
        # 생휴: 여성 간호사 월 1회 자동 (hard 요청으로 이미 counted된 경우 제외)
        if not nurses[ni].is_male and rules.menstrual_leave:
            auto_menst = max(0, _period_months - (1 if nurses[ni].menstrual_used else 0))
            already_menst = sum(
                1 for r in requests
                if r.nurse_id == nid and r.is_hard and r.code == "생휴"
                and 1 <= r.day <= num_days
            )
            hard_off += max(0, auto_menst - already_menst)

        # 수면: pending_sleep → 자동 1개, auto-수면 가능 간호사도 +1 (보수적 추정)
        sleep_already = sum(
            1 for r in requests
            if r.nurse_id == nid and r.is_hard and r.code == "수면"
            and 1 <= r.day <= num_days
        )
        if sleep_already == 0:
            if nurses[ni].pending_sleep:
                hard_off += 1
            else:
                # 짝수달 bimonthly 조건: eff_threshold ≤ max_N이면 수면 배정 가능성 있음
                _partner = get_sleep_partner_month(start_date.month)
                _eff_t = rules.sleep_N_monthly
                if _partner is not None:
                    _eff_t = min(_eff_t, max(0, rules.sleep_N_bimonthly - nurses[ni].prev_month_N))
                if 0 < _eff_t <= rules.max_N_per_month:
                    hard_off += 1  # auto-sleep 발생 가능

        # 법휴: 공휴일에 근무 못 하면 강제 법휴 → 최대 공휴일 수만큼 가산
        hard_off += len(public_holiday_dis)

        # NN 경계: prev_tail이 NN으로 끝나면 H6이 di=0·di=1 모두 off 강제
        # H11은 week 1에서 _OFF 1개만 요구 → di=0=_OFF, di=1=다른 off 타입 → 실제 off +1
        tail = nurses[ni].prev_tail_shifts or []
        if len(tail) >= 2 and tail[-2] == "N" and tail[-1] == "N":
            hard_off += 1

        return hard_off

    # H20 공차(tolerance): ±2 기본, 공휴일이 있으면 ±3으로 확장
    h20_tol = 3 if public_holiday_dis else 2

    h20_skip_count = 0
    h20_apply_count = 0
    for ni in regular_nis:
        if _expected_off_count(ni) > base_off + h20_tol:
            h20_skip_count += 1
            continue
        off_sum = sum(
            shifts[(ni, di, oi)]
            for di in range(num_days) for oi in ALL_OFF
        )
        model.add(off_sum >= base_off - h20_tol)
        model.add(off_sum <= base_off + h20_tol)
        h20_apply_count += 1

    if fourday_nis:
        fourday_target = base_off + extra_off_4day
        for ni in fourday_nis:
            if _expected_off_count(ni) > fourday_target + h20_tol:
                h20_skip_count += 1
                continue
            off_sum = sum(
                shifts[(ni, di, oi)]
                for di in range(num_days) for oi in ALL_OFF
            )
            model.add(off_sum >= fourday_target - h20_tol)
            model.add(off_sum <= fourday_target + h20_tol)
            h20_apply_count += 1

    _log(f"[H20] applied={h20_apply_count} skip={h20_skip_count} | base_off={base_off} tol=±{h20_tol}")

    # ── H21. 신청 휴무 샌드위치 금지 ──
    # 간호사가 d일에 휴무 신청 + d-1일·d+1일이 모두 휴무로 배정 → d일도 반드시 휴무
    # 패턴: 휴무(배정) - 근무(휴무신청 but 잘림) - 휴무(배정) 방지
    for ni in range(num_nurses):
        nid = nurses[ni].id
        for di in range(1, num_days - 1):
            r = req_map.get((nid, di + 1))  # day는 1-based
            if r is None or not r.is_off_request:
                continue
            is_off_d   = model.new_bool_var(f"is_off_n{ni}_d{di}")
            is_off_dm1 = model.new_bool_var(f"is_off_n{ni}_d{di-1}")
            is_off_dp1 = model.new_bool_var(f"is_off_n{ni}_d{di+1}")
            model.add(is_off_d   == sum(shifts[(ni, di,     oi)] for oi in ALL_OFF))
            model.add(is_off_dm1 == sum(shifts[(ni, di - 1, oi)] for oi in ALL_OFF))
            model.add(is_off_dp1 == sum(shifts[(ni, di + 1, oi)] for oi in ALL_OFF))
            # is_off[d-1] AND is_off[d+1] → is_off[d]
            # 동치: NOT(is_off[d-1]) OR NOT(is_off[d+1]) OR is_off[d]
            model.add_bool_or([is_off_dm1.Not(), is_off_dp1.Not(), is_off_d])
    _cp_idx["H21(샌드위치금지)"] = len(model.proto.constraints)

    # ══════════════════════════════════════════
    # SOFT CONSTRAINTS (목적함수)
    # ══════════════════════════════════════════
    obj = list(obj_auto_off)  # 생휴/수면 soft bonus 포함

    # ── S1. 희망 요청 반영 (condition/score 기반 가중치) ──
    # A조건: base 500 + score → 최솟값 약 400 (score 음수 시)
    # B조건: base 150 + score → 최댓값 250 (score 100 시)
    # A조건 최솟값 > B조건 최댓값 → A가 score와 무관하게 항상 B보다 우선
    # 공정성 페널티(-5~-8)보다 훨씬 높으므로 요청이 거의 항상 반영됨
    or_groups = {}      # (ni, di) → [shift_index, ...]
    or_weights = {}     # (ni, di) → weight
    for r in requests:
        if r.is_hard or r.is_exclude:
            continue
        if r.nurse_id not in nurse_idx:
            continue
        ni = nurse_idx[r.nurse_id]
        di = r.day - 1
        if di < 0 or di >= num_days:
            continue

        # A조건: 근무/OFF 모두 soft-high (800 + score*5), max 1300
        # B조건: soft (250 + score*5), max 750 — A보다 낮게 유지
        if r.condition == 'A':
            weight = 800 + r.score * 5
        else:
            weight = 250 + r.score * 5

        # OR 요청은 별도 그룹 처리
        if r.is_or:
            key = (ni, di)
            if key not in or_groups:
                or_groups[key] = []
                or_weights[key] = weight
            else:
                or_weights[key] = max(or_weights[key], weight)  # 같은 날 OR 중 최고 weight
            if r.code in NAME_TO_IDX:
                si = NAME_TO_IDX[r.code]
                or_groups[key].append(si)  # 정확히 그 코드만 매칭
            continue

        if r.code in NAME_TO_IDX:
            si = NAME_TO_IDX[r.code]
            # 정확히 신청 코드와 일치해야 보상 (OFF → _OFF만, 수면/생휴 등은 각각 별도 신청)
            obj.append(weight * shifts[(ni, di, si)])

    # ── S1a. OR 그룹 반영 (condition/score 가중치) ──
    # 하루에 shift는 1개만 → sum 최대 1 → 보상 1회
    for (ni, di), si_list in or_groups.items():
        unique_si = list(set(si_list))
        w = or_weights.get((ni, di), 650)  # 기본값: B조건 score 100 기준 (150 + 100*5)
        obj.append(w * sum(shifts[(ni, di, si)] for si in unique_si))

    # ── S1b. 하드 휴무 사이 빈날 → OFF/휴무 배치 선호 (+250) ──
    # 예: 5일=휴가, 7일=휴가인데 6일 요청 없음 → 6일에 OFF 배치 유도
    # (주당 OFF는 1개이므로 이 보너스로 솔버가 빈날을 OFF 위치로 선택)
    for ni in range(num_nurses):
        nid = nurses[ni].id
        # 이 간호사의 하드 휴무일 집합 (0-indexed di)
        hard_off_di: set[int] = set()
        for r in requests:
            if r.nurse_id != nid or not r.is_hard:
                continue
            di_r = r.day - 1
            if 0 <= di_r < num_days and r.code in NAME_TO_IDX:
                si_r = NAME_TO_IDX[r.code]
                if si_r in ALL_OFF:
                    hard_off_di.add(di_r)
        # 고정 주휴일도 포함
        if nurses[ni].fixed_weekly_off is not None:
            for di in range(num_days):
                if weekday_of(di) == nurses[ni].fixed_weekly_off:
                    hard_off_di.add(di)
        # 양쪽이 하드 휴무인 단일 빈날(갭)에 OFF 선호 보너스
        for di in range(1, num_days - 1):
            if di in hard_off_di:
                continue
            if (di - 1) in hard_off_di and (di + 1) in hard_off_di:
                obj.append(250 * sum(shifts[(ni, di, oi)] for oi in ALL_OFF))

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

    # ── S8. 월 N 초과 억제 (-300/개) ──
    # max_N_per_month(기본 6) 초과 시 강한 소프트 페널티
    # 하드 제약이 아니므로 인원 부족 시 초과 허용, 단 최대한 억제
    for ni in range(num_nurses):
        n_cnt = shift_counts[(ni, "N")]
        excess = model.new_int_var(0, num_days, f"N_excess_{ni}")
        model.add(excess >= n_cnt - rules.max_N_per_month)
        obj.append(-300 * excess)

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

    # ── S6. N 연속 배정 보상 (+20/쌍) ──
    # 연속된 N 쌍마다 보너스 → N 휴무 N 패턴 대신 N N N 블록 유도
    for ni in range(num_nurses):
        for di in range(num_days - 1):
            pair = model.new_bool_var(f"n_pair_{ni}_{di}")
            model.add_min_equality(pair, [shifts[(ni, di, _N)], shifts[(ni, di + 1, _N)]])
            obj.append(20 * pair)

    # ── S7. 연속 휴무 보상 (+15/쌍) ──
    # 연속된 휴무 쌍마다 보너스 → 산발적 휴무(D-OFF-D-OFF)보다 연속 휴무(D-D-OFF-OFF) 유도
    for ni in range(num_nurses):
        for di in range(num_days - 1):
            off_di  = sum(shifts[(ni, di,     oi)] for oi in ALL_OFF)
            off_di1 = sum(shifts[(ni, di + 1, oi)] for oi in ALL_OFF)
            both_off = model.new_bool_var(f"both_off_{ni}_{di}")
            model.add(both_off <= off_di)
            model.add(both_off <= off_di1)
            obj.append(15 * both_off)


    # ── 목적함수 설정 ──
    if obj:
        model.maximize(sum(obj))

    # ══════════════════════════════════════════
    # 솔버 실행
    # ══════════════════════════════════════════
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = timeout_seconds
    solver.parameters.num_workers = 8
    
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
    elif status == cp_model.INFEASIBLE:
        _log("해를 찾을 수 없습니다 (Infeasible). 원인 진단 시작...")
        _cp_idx["H20(휴무편차)"] = len(model.proto.constraints)
        _diagnose_infeasible(nurses, requests, rules, start_date, num_days, shifts, model, _cp_idx)
    else:
        _log(f"타임아웃 — 제한 시간 내에 해를 찾지 못했습니다 (status={status}). 타임아웃을 늘리거나 hard 신청(번표·수면·병가)을 확인하세요.")
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
