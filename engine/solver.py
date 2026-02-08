"""스케줄링 엔진 (Day 3에 OR-Tools 구현 예정, 현재는 기본 할당)"""
import calendar
import random
from engine.models import Nurse, Request, Rules, Schedule


def solve_schedule(
    nurses: list[Nurse],
    requests: list[Request],
    rules: Rules,
    year: int,
    month: int,
) -> Schedule:
    """근무표 자동 생성

    TODO (Day 3~4):
    - OR-Tools CP-SAT Solver로 교체
    - Hard Constraints 전체 구현
    - Soft Constraints 최적화

    현재: 기본 규칙만 적용한 간단한 할당 (테스트용)
    """
    schedule = Schedule(
        year=year, month=month,
        nurses=nurses, rules=rules, requests=requests,
    )
    num_days = schedule.num_days

    # 요청 맵: (nurse_id, day) → code
    req_map = {}
    for r in requests:
        req_map[(r.nurse_id, r.day)] = r

    # 간단한 할당 로직 (테스트용)
    for nurse in nurses:
        available_shifts = []
        if nurse.can_day:
            available_shifts.append("D")
        if nurse.can_evening:
            available_shifts.append("E")
        if nurse.can_night:
            available_shifts.append("N")

        if nurse.fixed_shift and nurse.fixed_shift in ("D", "E", "N"):
            available_shifts = [nurse.fixed_shift]

        off_count = 0
        consecutive_work = 0
        consecutive_night = 0
        prev_shift = None

        for d in range(1, num_days + 1):
            req = req_map.get((nurse.id, d))

            # 확정 요청 처리
            if req:
                if req.code in ("연차",):
                    schedule.set_shift(nurse.id, d, "OFF")
                    off_count += 1
                    consecutive_work = 0
                    consecutive_night = 0
                    prev_shift = "OFF"
                    continue
                elif req.code in ("D!", "E!", "N!"):
                    forced = req.code[0]
                    schedule.set_shift(nurse.id, d, forced)
                    consecutive_work += 1
                    consecutive_night = consecutive_night + 1 if forced == "N" else 0
                    prev_shift = forced
                    continue
                elif req.code == "OFF":
                    schedule.set_shift(nurse.id, d, "OFF")
                    off_count += 1
                    consecutive_work = 0
                    consecutive_night = 0
                    prev_shift = "OFF"
                    continue

            # 연속 근무 제한 → OFF
            if consecutive_work >= rules.max_consecutive_work:
                schedule.set_shift(nurse.id, d, "OFF")
                off_count += 1
                consecutive_work = 0
                consecutive_night = 0
                prev_shift = "OFF"
                continue

            # 연속 야간 후 OFF
            if consecutive_night >= rules.max_consecutive_night:
                schedule.set_shift(nurse.id, d, "OFF")
                off_count += 1
                consecutive_work = 0
                consecutive_night = 0
                prev_shift = "OFF"
                continue

            # 금지 패턴 필터
            day_shifts = list(available_shifts)
            if prev_shift == "N":
                if rules.ban_night_to_day and "D" in day_shifts:
                    day_shifts.remove("D")
                if rules.ban_night_to_evening and "E" in day_shifts:
                    day_shifts.remove("E")
            if prev_shift == "E":
                if rules.ban_evening_to_day and "D" in day_shifts:
                    day_shifts.remove("D")

            # 희망 요청 우선
            if req and req.code in ("D", "E", "N") and req.code in day_shifts:
                chosen = req.code
            elif day_shifts:
                # OFF를 적절히 배분
                target_off = rules.min_monthly_off
                remaining_days = num_days - d + 1
                needed_off = max(0, target_off - off_count)
                off_prob = needed_off / max(remaining_days, 1)

                if random.random() < off_prob:
                    chosen = "OFF"
                else:
                    chosen = random.choice(day_shifts)
            else:
                chosen = "OFF"

            schedule.set_shift(nurse.id, d, chosen)

            if chosen == "OFF":
                off_count += 1
                consecutive_work = 0
                consecutive_night = 0
            else:
                consecutive_work += 1
                consecutive_night = consecutive_night + 1 if chosen == "N" else 0

            prev_shift = chosen

    # 프리셉터 페어링 처리 (간단 버전)
    for nurse in nurses:
        if nurse.preceptor_of is not None:
            target = next((n for n in nurses if n.id == nurse.preceptor_of), None)
            if target:
                for d in range(1, num_days + 1):
                    preceptor_shift = schedule.get_shift(nurse.id, d)
                    schedule.set_shift(target.id, d, preceptor_shift)

    return schedule
