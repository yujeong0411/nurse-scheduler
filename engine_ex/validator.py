"""규칙 위반 검증 (수동 수정 시 사용)"""
from engine.models import Nurse, Rules, Schedule


def validate_change(
    schedule: Schedule,
    nurse: Nurse,
    day: int,
    new_shift: str,
    rules: Rules,
) -> list[str]:
    """근무 변경 시 규칙 위반 목록 반환. 빈 리스트 = 문제없음."""
    violations = []
    num_days = schedule.num_days

    # 1. 가능 근무 체크
    if new_shift == "D" and not nurse.can_day:
        violations.append(f"{nurse.name}은(는) Day 근무 불가")
    if new_shift == "E" and not nurse.can_evening:
        violations.append(f"{nurse.name}은(는) Evening 근무 불가")
    if new_shift == "N" and not nurse.can_night:
        violations.append(f"{nurse.name}은(는) Night 근무 불가 (야간 금지)")

    # 1-1. 평일만 근무 체크
    if nurse.weekday_only and new_shift != "OFF" and schedule.is_weekend(day):
        violations.append(f"{nurse.name}은(는) 평일만 근무 (주말 근무 불가)")

    # 2. 금지 패턴 (전날 → 오늘)
    if day > 1:
        prev = schedule.get_shift(nurse.id, day - 1)
        if prev == "N" and new_shift == "D" and rules.ban_night_to_day:
            violations.append("금지 패턴: Night 다음날 Day")
        if prev == "N" and new_shift == "E" and rules.ban_night_to_evening:
            violations.append("금지 패턴: Night 다음날 Evening")
        if prev == "E" and new_shift == "D" and rules.ban_evening_to_day:
            violations.append("금지 패턴: Evening 다음날 Day")

    # 3. 금지 패턴 (오늘 → 다음날)
    if day < num_days:
        next_s = schedule.get_shift(nurse.id, day + 1)
        if new_shift == "N" and next_s == "D" and rules.ban_night_to_day:
            violations.append("금지 패턴: Night 다음날 Day (다음날 영향)")
        if new_shift == "N" and next_s == "E" and rules.ban_night_to_evening:
            violations.append("금지 패턴: Night 다음날 Evening (다음날 영향)")
        if new_shift == "E" and next_s == "D" and rules.ban_evening_to_day:
            violations.append("금지 패턴: Evening 다음날 Day (다음날 영향)")

    # 4. 연속 근무 체크
    if new_shift != "OFF":
        consec = 1
        # 앞으로
        for dd in range(day - 1, 0, -1):
            if schedule.get_shift(nurse.id, dd) != "OFF":
                consec += 1
            else:
                break
        # 뒤로
        for dd in range(day + 1, num_days + 1):
            if schedule.get_shift(nurse.id, dd) != "OFF":
                consec += 1
            else:
                break
        if consec > rules.max_consecutive_work:
            violations.append(f"연속 근무 {consec}일 (최대 {rules.max_consecutive_work}일)")

    # 5. 연속 야간 체크
    if new_shift == "N":
        consec_n = 1
        for dd in range(day - 1, 0, -1):
            if schedule.get_shift(nurse.id, dd) == "N":
                consec_n += 1
            else:
                break
        for dd in range(day + 1, num_days + 1):
            if schedule.get_shift(nurse.id, dd) == "N":
                consec_n += 1
            else:
                break
        if consec_n > rules.max_consecutive_night:
            violations.append(f"연속 야간 {consec_n}일 (최대 {rules.max_consecutive_night}일)")

    # 6. 최소 인원 체크 (변경으로 인원 부족해지는 경우)
    old_shift = schedule.get_shift(nurse.id, day)
    is_weekend = schedule.is_weekend(day)

    if old_shift in ("D", "E", "N") and new_shift != old_shift:
        old_count = schedule.get_staff_count(day, old_shift)
        # 본인이 빠지면 -1
        new_count = old_count - 1
        min_req = rules.get_min_staff(old_shift, is_weekend)
        if new_count < min_req:
            violations.append(
                f"{old_shift} 인원 부족: {new_count}명 (최소 {min_req}명 필요)"
            )

    # 7. 프리셉터 페어 체크
    if nurse.preceptor_of is not None:
        target_shift = schedule.get_shift(nurse.preceptor_of, day)
        if target_shift and target_shift != new_shift:
            violations.append(
                f"프리셉터 페어 불일치: 신규 간호사는 {target_shift}, 변경하려는 근무는 {new_shift}"
            )

    # 역방향: 이 간호사가 누군가의 프리셉터 대상인 경우
    for n in schedule.nurses:
        if n.preceptor_of == nurse.id:
            preceptor_shift = schedule.get_shift(n.id, day)
            if preceptor_shift and preceptor_shift != new_shift:
                violations.append(
                    f"프리셉터 페어 불일치: 프리셉터({n.name})는 {preceptor_shift}"
                )

    return violations
