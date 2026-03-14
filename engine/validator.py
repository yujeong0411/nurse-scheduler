"""수동 수정 시 규칙 위반 검증 — 응급실 간호사 근무표 (D/E/N)

검증 항목 (21개):
 1-2. 역순 금지 (전날→오늘, 오늘→다음날)
 3.   연속 근무 ≤5일
 4.   연속 N ≤3개
 5.   NN 후 휴무 2일
 6.   월 N ≤6개
 7.   주당 휴무 ≥2개
 8.   일일 인원 (D≥7, E≥8, N≥7)
 9.   책임 ≥1
 10.  책임+서브차지 ≥2
 11.  ROLE_TIERS 누적 제한
 12.  책임만 ≤1
 13.  법정공휴일 휴무 = 법휴/주
 14.  주4일제 주당 OFF ≥3
 15.  임산부 연속 근무 ≤4
 16.  N→1휴무→(D/D9/D1/중1/중2) 금지 — 1휴무 후 E·N만 허용
 16b. N 다음날 보수/필수/번표 금지
 17.  휴가 잔여일 초과
 18.  고정 주휴 요일 위반
 19.  생휴: 남성 불가, 같은 달 1회 초과 금지
 20.  POFF: 임산부만
 21.  중2: 역할 '중2'만, 주말 불가
"""
from datetime import timedelta
from engine.models import (
    Nurse, Rules, Schedule,
    WORK_SHIFTS, OFF_TYPES, SHIFT_ORDER, ROLE_TIERS,
)


def validate_change(
    schedule: Schedule,
    nurse: Nurse,
    day: int,
    new_shift: str,
    rules: Rules,
) -> list[str]:
    """수동 수정 시 규칙 위반 체크

    Args:
        schedule: 현재 근무표 (수정 전)
        nurse: 대상 간호사
        day: 대상 날짜 (1-based)
        new_shift: 새 근무코드
        rules: 규칙

    Returns:
        위반 메시지 리스트 (빈 리스트 = 문제 없음)
    """
    violations = []
    nid = nurse.id
    num_days = schedule.num_days
    old_shift = schedule.get_shift(nid, day)

    is_work = new_shift in WORK_SHIFTS
    is_off = new_shift in OFF_TYPES or new_shift == "OFF"

    # ── 1-2. 역순 금지 ──
    if is_work and rules.ban_reverse_order:
        # 전날 → 오늘
        if day > 1:
            prev = schedule.get_shift(nid, day - 1)
            if prev in SHIFT_ORDER and new_shift in SHIFT_ORDER:
                if SHIFT_ORDER[prev] > SHIFT_ORDER[new_shift]:
                    violations.append(
                        f"역순 금지: {day-1}일 {prev} → {day}일 {new_shift}"
                    )

        # 오늘 → 다음날
        if day < num_days:
            nxt = schedule.get_shift(nid, day + 1)
            if nxt in SHIFT_ORDER and new_shift in SHIFT_ORDER:
                if SHIFT_ORDER[new_shift] > SHIFT_ORDER[nxt]:
                    violations.append(
                        f"역순 금지: {day}일 {new_shift} → {day+1}일 {nxt}"
                    )

    # ── 3. 연속 근무 ≤5일 ──
    if is_work:
        consec = 1
        # 앞으로
        d = day - 1
        while d >= 1 and schedule.get_shift(nid, d) in WORK_SHIFTS:
            consec += 1
            d -= 1
        # 뒤로
        d = day + 1
        while d <= num_days and schedule.get_shift(nid, d) in WORK_SHIFTS:
            consec += 1
            d += 1

        if consec > rules.max_consecutive_work:
            violations.append(
                f"연속 근무 {consec}일 (최대 {rules.max_consecutive_work}일)"
            )

    # ── 4. 연속 N ≤3개 ──
    if new_shift == "N":
        consec_n = 1
        d = day - 1
        while d >= 1 and schedule.get_shift(nid, d) == "N":
            consec_n += 1
            d -= 1
        d = day + 1
        while d <= num_days and schedule.get_shift(nid, d) == "N":
            consec_n += 1
            d += 1

        if consec_n > rules.max_consecutive_N:
            violations.append(
                f"연속 N {consec_n}개 (최대 {rules.max_consecutive_N}개)"
            )

    # ── 5. NN/NNN 후 휴무 ──
    # N을 놓을 때: 형성되는 N-블록(길이≥2)의 끝 이후 off_after일 확인
    if new_shift == "N":
        # 블록 끝 탐색 (day 포함, 오른쪽으로 확장)
        block_end = day
        while block_end < num_days and schedule.get_shift(nid, block_end + 1) == "N":
            block_end += 1
        # 블록 시작 탐색 (day 포함, 왼쪽으로 확장)
        block_start = day
        while block_start > 1 and schedule.get_shift(nid, block_start - 1) == "N":
            block_start -= 1
        block_len = block_end - block_start + 1
        if block_len >= 2:
            for k in range(rules.off_after_2N):
                check = block_end + 1 + k
                if check <= num_days:
                    if schedule.get_shift(nid, check) in WORK_SHIFTS:
                        violations.append(
                            f"N {block_len}연속 후 {check}일에 근무 있음 "
                            f"(휴무 {rules.off_after_2N}일 필요)"
                        )
                        break

    # 근무→근무 or OFF→근무 변경 시: 앞 off_after일 내에 NN 이상 블록 끝이 있으면 위반
    if is_work and old_shift not in WORK_SHIFTS:
        for end in range(day - 1, max(0, day - rules.off_after_2N - 1), -1):
            if end >= 2:
                s_end = schedule.get_shift(nid, end)
                s_prev = schedule.get_shift(nid, end - 1)
                s_after = schedule.get_shift(nid, end + 1) if end + 1 <= num_days else None
                if (s_end == "N" and s_prev == "N"
                        and (s_after is None or s_after != "N")):
                    gap = day - end - 1
                    violations.append(
                        f"{end-1}~{end}일 N연속 후 "
                        f"휴무 {rules.off_after_2N - gap}일 더 필요"
                    )
                    break

    # ── 6. 월 N ≤6개 ──
    if new_shift == "N":
        n_count = sum(
            1 for d in range(1, num_days + 1)
            if d != day and schedule.get_shift(nid, d) == "N"
        ) + 1
        if n_count > rules.max_N_per_month:
            violations.append(
                f"월 N {n_count}개 (최대 {rules.max_N_per_month}개)"
            )

    # ── 7. 주당 휴무 ≥2개 ──
    if is_work and old_shift not in WORK_SHIFTS:
        # OFF → 근무 변경: 해당 주 휴무 감소
        week_start = ((day - 1) // 7) * 7 + 1
        week_end = min(week_start + 6, num_days)
        off_count = sum(
            1 for d in range(week_start, week_end + 1)
            if d != day and schedule.get_shift(nid, d) not in WORK_SHIFTS
        )
        if off_count < rules.min_weekly_off:
            violations.append(
                f"{week_start}~{week_end}일 주간 휴무 {off_count}일 "
                f"(최소 {rules.min_weekly_off}일)"
            )

    # ── 8. 일일 인원 ──
    # 근무 → 다른 근무/OFF: 원래 근무 인원 감소 확인
    if old_shift in ("D", "중2", "E", "N") and old_shift != new_shift:
        count = schedule.get_staff_count(day, old_shift) - 1
        min_req = getattr(rules, f"daily_{old_shift}")
        if count < min_req:
            violations.append(
                f"{old_shift} 인원 부족: {count}명 (최소 {min_req}명)"
            )

    # ── 9. 책임 ≥1 ──
    if nurse.grade == "책임" and is_off:
        if old_shift in ("D", "중2", "E", "N"):
            chief_cnt = sum(
                1 for n in schedule.nurses
                if n.id != nid
                and n.grade == "책임"
                and schedule.get_shift(n.id, day) == old_shift
            )
            if chief_cnt < rules.min_chief_per_shift:
                violations.append(
                    f"{day}일 {old_shift} 책임 부족: {chief_cnt}명 "
                    f"(최소 {rules.min_chief_per_shift}명)"
                )

    # ── 10. 책임+서브차지 ≥2 ──
    if nurse.grade in ("책임", "서브차지") and is_off:
        if old_shift in ("D", "중2", "E", "N"):
            sr_cnt = sum(
                1 for n in schedule.nurses
                if n.id != nid
                and n.grade in ("책임", "서브차지")
                and schedule.get_shift(n.id, day) == old_shift
            )
            if sr_cnt < rules.min_senior_per_shift:
                violations.append(
                    f"{day}일 {old_shift} 시니어 부족: {sr_cnt}명 "
                    f"(최소 {rules.min_senior_per_shift}명)"
                )

    # ── 11. ROLE_TIERS 누적 제한 ──
    # 중간근무 추가 시: (역할셋, max_d, max_m, max_e, max_n)
    if is_work and nurse.role:
        for tier_roles, max_d, max_e, max_n in ROLE_TIERS:
            if nurse.role not in tier_roles:
                continue
            limits = {"D": max_d, "E": max_e, "N": max_n}
            # 중간근무 추가 시: "M" 키로 중간계열 통합 체크
            if new_shift in limits:
                cnt = sum(
                    1 for n in schedule.nurses
                    if n.id != nid
                    and n.role in tier_roles
                    and schedule.get_shift(n.id, day) == new_shift
                ) + 1
                if cnt > limits[new_shift]:
                    violations.append(
                        f"{day}일 {new_shift} 역할 초과: "
                        f"{tier_roles} {cnt}명 (최대 {limits[new_shift]}명)"
                    )

    # ── 12. 책임만 ≤1 ──
    if is_work and nurse.role == "책임만":
        cnt = sum(
            1 for n in schedule.nurses
            if n.id != nid
            and n.role == "책임만"
            and schedule.get_shift(n.id, day) == new_shift
        ) + 1
        if cnt > 1:
            violations.append(f"{day}일 {new_shift} 책임만 {cnt}명 (최대 1명)")

    # ── 13. 법정공휴일 ──
    if day in rules.public_holidays and is_off:
        if new_shift not in ("법휴", "주"):
            violations.append(
                f"{day}일은 법정공휴일: 법휴 또는 주만 가능"
            )

    # ── 14. 주4일제 ──
    if nurse.is_4day_week and is_work and old_shift not in WORK_SHIFTS:
        week_start = ((day - 1) // 7) * 7 + 1
        week_end = min(week_start + 6, num_days)
        off_count = sum(
            1 for d in range(week_start, week_end + 1)
            if d != day and schedule.get_shift(nid, d) not in WORK_SHIFTS
        )
        if off_count < 3:
            violations.append(
                f"주4일제: {week_start}~{week_end}일 휴무 {off_count}일 "
                f"(최소 3일)"
            )

    # ── 15. 임산부 연속 근무 ≤4 ──
    if nurse.is_pregnant and is_work:
        consec = 1
        d = day - 1
        while d >= 1 and schedule.get_shift(nid, d) in WORK_SHIFTS:
            consec += 1
            d -= 1
        d = day + 1
        while d <= num_days and schedule.get_shift(nid, d) in WORK_SHIFTS:
            consec += 1
            d += 1
        if consec > rules.pregnant_poff_interval:
            violations.append(
                f"임산부 연속 근무 {consec}일 "
                f"(최대 {rules.pregnant_poff_interval}일)"
            )

    # ── 16. N→1off→(D/중간근무) 금지 ──
    # N 후 1휴무 뒤에는 E·N만 허용
    _MID_AND_D = {"D", "D9", "D1", "중1", "중2"}
    # D/중간으로 변경 시: 2일 전이 N이고 사이가 휴무면 위반
    if new_shift in _MID_AND_D and day >= 3:
        prev2 = schedule.get_shift(nid, day - 2)
        prev1 = schedule.get_shift(nid, day - 1)
        if prev2 == "N" and prev1 not in WORK_SHIFTS:
            violations.append(
                f"N→1휴무→{new_shift} 금지: {day-2}일 N → {day-1}일 {prev1} → {day}일 {new_shift}"
            )
    # N으로 변경 시: 2일 후가 D/중간이고 사이가 휴무면 위반
    if new_shift == "N" and day + 2 <= num_days:
        next1 = schedule.get_shift(nid, day + 1)
        next2 = schedule.get_shift(nid, day + 2)
        if next2 in _MID_AND_D and next1 not in WORK_SHIFTS:
            violations.append(
                f"N→1휴무→{next2} 금지: {day}일 N → {day+1}일 {next1} → {day+2}일 {next2}"
            )
    # 근무→OFF 변경 시: 양쪽이 N, D/중간이면 위반
    if is_off and old_shift in WORK_SHIFTS:
        if day >= 2 and day < num_days:
            prev = schedule.get_shift(nid, day - 1)
            nxt = schedule.get_shift(nid, day + 1)
            if prev == "N" and nxt in _MID_AND_D:
                violations.append(
                    f"N→1휴무→{nxt} 금지: {day-1}일 N → {day}일 {new_shift} → {day+1}일 {nxt}"
                )

    # ── 16b. N 다음날 보수/필수/번표 금지 ──
    _N_INVALID_NEXT = {"보수", "필수", "번표"}
    # 오늘이 보수/필수/번표로 변경: 전날이 N이면 위반
    if new_shift in _N_INVALID_NEXT and day >= 2:
        prev = schedule.get_shift(nid, day - 1)
        if prev == "N":
            violations.append(
                f"N 후 {new_shift} 금지: {day-1}일 N → {day}일 {new_shift}"
            )
    # 오늘이 N으로 변경: 다음날이 보수/필수/번표이면 위반
    if new_shift == "N" and day < num_days:
        nxt = schedule.get_shift(nid, day + 1)
        if nxt in _N_INVALID_NEXT:
            violations.append(
                f"N 후 {nxt} 금지: {day}일 N → {day+1}일 {nxt}"
            )

    # ── 17. 휴가 잔여일 ──
    if new_shift == "휴가":
        used = sum(
            1 for d in range(1, num_days + 1)
            if d != day and schedule.get_shift(nid, d) == "휴가"
        ) + 1
        if used > nurse.vacation_days:
            violations.append(
                f"휴가 {used}일 사용 (잔여 {nurse.vacation_days}일)"
            )

    # ── 18. 고정 주휴 요일 ──
    if nurse.fixed_weekly_off is not None:
        day_weekday = (schedule.start_date + timedelta(days=day - 1)).weekday()
        if day_weekday == nurse.fixed_weekly_off and new_shift != "주":
            weekday_names = ["월", "화", "수", "목", "금", "토", "일"]
            violations.append(
                f"{day}일은 고정 주휴일 ({weekday_names[nurse.fixed_weekly_off]}요일): "
                f"'주' 필요 (현재: {new_shift})"
            )

    # ── 19. 생휴: 남성 불가, 월 1회 초과 금지 ──
    if new_shift == "생휴":
        if nurse.is_male:
            violations.append("생리휴가는 남성에게 배정할 수 없습니다")
        else:
            target_month = (schedule.start_date + timedelta(days=day - 1)).month
            # 이전 근무표에서 시작 달(첫째 달)에 이미 생휴 사용 여부
            is_start_month = target_month == schedule.start_date.month
            already_used_prev = nurse.menstrual_used and is_start_month
            # 현재 근무표 내 같은 달의 생휴 수 (오늘 제외)
            same_month_count = sum(
                1 for d in range(1, num_days + 1)
                if d != day
                and schedule.get_shift(nid, d) == "생휴"
                and (schedule.start_date + timedelta(days=d - 1)).month == target_month
            )
            if already_used_prev:
                violations.append(
                    f"생리휴가는 이미 이전 근무표에서 {target_month}월에 사용했습니다"
                )
            elif same_month_count >= 1:
                violations.append(
                    f"생리휴가는 같은 달에 1회만 허용됩니다 (이미 {same_month_count}회 사용)"
                )

    # ── 20. POFF: 임산부만 ──
    if new_shift == "POFF" and not nurse.is_pregnant:
        violations.append("POFF(임산부 보호)는 임산부에게만 배정할 수 있습니다")

    # ── 21. 중2: 역할 '중2'만, 주말 불가 ──
    if new_shift == "중2":
        if nurse.role != "중2":
            violations.append(f"중2 근무는 역할이 '중2'인 간호사만 배정 가능합니다 (현재 역할: {nurse.role or '없음'})")
        day_weekday = (schedule.start_date + timedelta(days=day - 1)).weekday()
        if day_weekday >= 5:  # 토=5, 일=6
            weekday_names = ["월", "화", "수", "목", "금", "토", "일"]
            violations.append(f"중2 근무는 주말({weekday_names[day_weekday]})에 배정할 수 없습니다")

    return violations
