"""공정성 점수 평가 — 응급실 간호사 근무표 (D/E/N)"""
from engine.models import (
    Schedule, Rules, WORK_SHIFTS, OFF_TYPES, SHIFT_ORDER, ROLE_TIERS,
)


def evaluate_schedule(schedule: Schedule, rules: Rules) -> dict:
    """근무표 공정성 종합 평가"""
    nurses = schedule.nurses
    num_days = schedule.num_days

    empty_result = {
        "grade": "-", "score": 0, "shift_stats": {},
        "d_deviation": 0, "e_deviation": 0, "n_deviation": 0,
        "night_deviation": 0, "weekend_deviation": 0,
        "bad_patterns": {}, "request_fulfilled": {"total": 0, "fulfilled": 0, "rate": 0},
        "rule_violations": 0,
    }

    if not nurses or not schedule.schedule_data:
        return empty_result

    # ── 개인별 근무 횟수 ──
    # 중간근무 추가 시: "M": 0 추가, shift in ("D9","D1","중1","중2") → M
    shift_stats = {}
    for nurse in nurses:
        stats = {"D": 0, "E": 0, "N": 0, "OFF": 0, "총근무": 0}
        # stats = {"D": 0, "M": 0, "E": 0, "N": 0, "OFF": 0, "총근무": 0}
        for d in range(1, num_days + 1):
            s = schedule.get_shift(nurse.id, d)
            if s == "D":
                stats["D"] += 1
            elif s == "E":
                stats["E"] += 1
            elif s == "N":
                stats["N"] += 1
            # elif s in ("D9", "D1", "중1", "중2"):  # 중간근무 추가 시
            #     stats["M"] += 1
            else:
                stats["OFF"] += 1
        stats["총근무"] = stats["D"] + stats["E"] + stats["N"]  # + stats["M"]
        shift_stats[nurse.id] = stats

    # ── 편차 ──
    def deviation(values):
        if not values or len(values) < 2:
            return 0
        return max(values) - min(values)

    d_dev = deviation([shift_stats[n.id]["D"] for n in nurses])
    # m_dev = deviation([shift_stats[n.id]["M"] for n in nurses])  # 중간근무 추가 시
    e_dev = deviation([shift_stats[n.id]["E"] for n in nurses])
    n_dev = deviation([shift_stats[n.id]["N"] for n in nurses])
    night_deviation = n_dev

    # ── 주말 편차 ──
    weekend_days = [d for d in range(1, num_days + 1) if schedule.is_weekend(d)]
    weekend_counts = []
    for nurse in nurses:
        wk = sum(
            1 for d in weekend_days
            if schedule.get_shift(nurse.id, d) in WORK_SHIFTS
        )
        weekend_counts.append(wk)
    weekend_deviation = deviation(weekend_counts)

    # ── 역순 패턴 ──
    bad_patterns = {}
    for nurse in nurses:
        for d in range(1, num_days):
            s1 = schedule.get_shift(nurse.id, d)
            s2 = schedule.get_shift(nurse.id, d + 1)
            if s1 in SHIFT_ORDER and s2 in SHIFT_ORDER:
                if SHIFT_ORDER[s1] > SHIFT_ORDER[s2]:
                    key = f"{s1}→{s2}"
                    bad_patterns[key] = bad_patterns.get(key, 0) + 1

    # ── 요청 반영률 ──
    req_total = 0
    req_fulfilled = 0
    for r in schedule.requests:
        if r.is_hard or r.is_exclude:
            continue
        req_total += 1
        actual = schedule.get_shift(r.nurse_id, r.day)
        if r.code == "OFF" and actual in OFF_TYPES:
            req_fulfilled += 1
        elif actual == r.code:
            req_fulfilled += 1
    req_rate = req_fulfilled / req_total if req_total > 0 else 1.0

    # ── 규칙 위반 건수 ──
    rule_violations = 0

    for nurse in nurses:
        nid = nurse.id

        # 연속 근무
        consec = 0
        for d in range(1, num_days + 1):
            if schedule.get_shift(nid, d) in WORK_SHIFTS:
                consec += 1
                if consec > rules.max_consecutive_work:
                    rule_violations += 1
            else:
                consec = 0

        # 연속 N
        consec_n = 0
        for d in range(1, num_days + 1):
            if schedule.get_shift(nid, d) == "N":
                consec_n += 1
                if consec_n > rules.max_consecutive_N:
                    rule_violations += 1
            else:
                consec_n = 0

        # 월 N 제한
        if shift_stats[nid]["N"] > rules.max_N_per_month:
            rule_violations += 1

        # NN 후 휴무
        for d in range(1, num_days - 1):
            if (schedule.get_shift(nid, d) == "N" and
                    schedule.get_shift(nid, d + 1) == "N"):
                for k in range(rules.off_after_2N):
                    check = d + 2 + k
                    if check <= num_days:
                        if schedule.get_shift(nid, check) in WORK_SHIFTS:
                            rule_violations += 1

    # 일일 인원
    # 중간근무 추가 시: m_staff, rules.daily_M 체크 추가
    for d in range(1, num_days + 1):
        d_staff = schedule.get_staff_count(d, "D")
        e_staff = schedule.get_staff_count(d, "E")
        n_staff = schedule.get_staff_count(d, "N")
        if d_staff < rules.daily_D:
            rule_violations += 1
        if e_staff < rules.daily_E:
            rule_violations += 1
        if n_staff < rules.daily_N:
            rule_violations += 1

    # 직급
    # 중간근무 추가 시: ["D", "M", "E", "N"] + M은 중간계열 통합 카운트
    for d in range(1, num_days + 1):
        for shift_type in ["D", "E", "N"]:
            chief_cnt = sum(
                1 for n in nurses
                if n.grade == "책임"
                and schedule.get_shift(n.id, d) == shift_type
            )
            senior_cnt = sum(
                1 for n in nurses
                if n.grade in ("책임", "서브차지")
                and schedule.get_shift(n.id, d) == shift_type
            )
            if chief_cnt < rules.min_chief_per_shift:
                rule_violations += 1
            if senior_cnt < rules.min_senior_per_shift:
                rule_violations += 1

    # ── 종합 점수 (감점 내역 포함) ──
    score = 100.0
    deductions = []  # (항목, 감점, 상세)

    # 근무 편차 (D/E/N)
    shift_penalty = min((d_dev + e_dev + n_dev) * 3, 30)
    if shift_penalty > 0:
        score -= shift_penalty
        details = []
        if d_dev > 0:
            details.append(f"D편차 {d_dev}")
        if e_dev > 0:
            details.append(f"E편차 {e_dev}")
        if n_dev > 0:
            details.append(f"N편차 {n_dev}")
        deductions.append((
            "근무 편차", shift_penalty,
            f"{', '.join(details)} → 편차 합계 {d_dev+e_dev+n_dev} × 3 = {(d_dev+e_dev+n_dev)*3} (최대 -30)"
        ))

    # N 편차
    night_penalty = min(night_deviation * 5, 15)
    if night_penalty > 0:
        score -= night_penalty
        n_counts = [shift_stats[n.id]["N"] for n in nurses]
        deductions.append((
            "야간(N) 편차", night_penalty,
            f"N 최소 {min(n_counts)} ~ 최대 {max(n_counts)} (편차 {night_deviation}) × 5 = {night_deviation*5} (최대 -15)"
        ))

    # 주말 편차
    wk_penalty = min(weekend_deviation * 4, 15)
    if wk_penalty > 0:
        score -= wk_penalty
        deductions.append((
            "주말근무 편차", wk_penalty,
            f"주말근무 최소 {min(weekend_counts)} ~ 최대 {max(weekend_counts)} (편차 {weekend_deviation}) × 4 = {weekend_deviation*4} (최대 -15)"
        ))

    # 역순 패턴
    bad_total = sum(bad_patterns.values())
    bad_penalty = min(bad_total * 5, 15)
    if bad_penalty > 0:
        score -= bad_penalty
        pat_str = ", ".join(f"{k} {v}건" for k, v in bad_patterns.items())
        deductions.append((
            "역순 패턴", bad_penalty,
            f"{pat_str} → 총 {bad_total}건 × 5 = {bad_total*5} (최대 -15)"
        ))

    # 요청 반영률
    req_penalty = round((1 - req_rate) * 15, 1)
    if req_penalty > 0:
        score -= req_penalty
        deductions.append((
            "요청 미반영", req_penalty,
            f"반영 {req_fulfilled}/{req_total} ({round(req_rate*100,1)}%) → 미반영률 {round((1-req_rate)*100,1)}% × 15 = -{req_penalty}"
        ))

    # 규칙 위반
    viol_penalty = min(rule_violations * 3, 10)
    if viol_penalty > 0:
        score -= viol_penalty

    # 규칙 위반 상세 집계
    violation_details = []
    for nurse in nurses:
        nid = nurse.id
        # 연속 근무 초과
        consec = 0
        for d in range(1, num_days + 1):
            if schedule.get_shift(nid, d) in WORK_SHIFTS:
                consec += 1
                if consec == rules.max_consecutive_work + 1:
                    violation_details.append(f"{nurse.name}: {d}일 연속근무 {consec}일 초과")
            else:
                consec = 0

        # 연속 N 초과
        consec_n = 0
        for d in range(1, num_days + 1):
            if schedule.get_shift(nid, d) == "N":
                consec_n += 1
                if consec_n == rules.max_consecutive_N + 1:
                    violation_details.append(f"{nurse.name}: {d}일 연속N {consec_n}회 초과")
            else:
                consec_n = 0

        # 월 N 초과
        if shift_stats[nid]["N"] > rules.max_N_per_month:
            violation_details.append(f"{nurse.name}: 월N {shift_stats[nid]['N']}회 (최대 {rules.max_N_per_month})")

    # 일일 인원 부족
    for d in range(1, num_days + 1):
        for st, req_val in [("D", rules.daily_D), ("E", rules.daily_E), ("N", rules.daily_N)]:
            cnt = schedule.get_staff_count(d, st)
            if cnt < req_val:
                violation_details.append(f"{d}일 {st} 인원 {cnt}명 (필요 {req_val})")

    if viol_penalty > 0:
        deductions.append((
            "규칙 위반", viol_penalty,
            f"총 {rule_violations}건 × 3 = {rule_violations*3} (최대 -10)\n" +
            "\n".join(f"  · {v}" for v in violation_details[:10]) +
            (f"\n  ... 외 {len(violation_details)-10}건" if len(violation_details) > 10 else "")
        ))

    score = max(0, round(score, 1))

    if score >= 90:
        grade = "A"
    elif score >= 80:
        grade = "B+"
    elif score >= 70:
        grade = "B"
    elif score >= 60:
        grade = "C"
    elif score >= 50:
        grade = "D"
    else:
        grade = "F"

    return {
        "grade": grade,
        "score": score,
        "shift_stats": shift_stats,
        "d_deviation": d_dev,
        # "m_deviation": m_dev,  # 중간근무 추가 시
        "e_deviation": e_dev,
        "n_deviation": n_dev,
        "night_deviation": night_deviation,
        "weekend_deviation": weekend_deviation,
        "bad_patterns": bad_patterns,
        "request_fulfilled": {
            "total": req_total,
            "fulfilled": req_fulfilled,
            "rate": round(req_rate * 100, 1),
        },
        "rule_violations": rule_violations,
        "deductions": deductions,
        "violation_details": violation_details,
    }
