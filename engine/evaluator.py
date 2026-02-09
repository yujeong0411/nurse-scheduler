"""공정성 점수 평가"""
import calendar
from engine.models import Schedule, Rules


def evaluate_schedule(schedule: Schedule, rules: Rules) -> dict:
    """근무표 공정성 종합 평가

    Returns:
        {
            "grade": "A" ~ "F",
            "score": 0~100,
            "shift_stats": {nurse_id: {"D":n, "E":n, "N":n, "OFF":n}},
            "night_deviation": float,
            "weekend_deviation": float,
            "bad_patterns": {"N→D": n, "E→D": n, ...},
            "request_fulfilled": {"total": n, "fulfilled": n, "rate": float},
        }
    """
    nurses = schedule.nurses
    num_days = schedule.num_days

    if not nurses or not schedule.schedule_data:
        return {"grade": "-", "score": 0, "shift_stats": {},
                "night_deviation": 0, "weekend_deviation": 0,
                "bad_patterns": {}, "request_fulfilled": {"total": 0, "fulfilled": 0, "rate": 0}}

    # ── 개인별 근무 횟수 ──
    shift_stats = {}
    for nurse in nurses:
        stats = {"D": 0, "E": 0, "N": 0, "OFF": 0}
        for d in range(1, num_days + 1):
            s = schedule.get_shift(nurse.id, d)
            if s in stats:
                stats[s] += 1
        shift_stats[nurse.id] = stats

    # ── 야간 편차 ──
    night_counts = [shift_stats[n.id]["N"] for n in nurses if n.can_night]
    night_deviation = (max(night_counts) - min(night_counts)) if night_counts else 0

    # ── 주말 편차 ──
    weekend_days = [d for d in range(1, num_days + 1) if schedule.is_weekend(d)]
    weekend_counts = []
    for nurse in nurses:
        wk = sum(1 for d in weekend_days if schedule.get_shift(nurse.id, d) != "OFF")
        weekend_counts.append(wk)
    weekend_deviation = (max(weekend_counts) - min(weekend_counts)) if weekend_counts else 0

    # ── 기피 패턴 ──
    bad_patterns = {}
    for nurse in nurses:
        for d in range(1, num_days):
            s1 = schedule.get_shift(nurse.id, d)
            s2 = schedule.get_shift(nurse.id, d + 1)
            if s1 == "N" and s2 == "D":
                bad_patterns["N→D"] = bad_patterns.get("N→D", 0) + 1
            if s1 == "N" and s2 == "E":
                bad_patterns["N→E"] = bad_patterns.get("N→E", 0) + 1
            if s1 == "E" and s2 == "D":
                bad_patterns["E→D"] = bad_patterns.get("E→D", 0) + 1

    # ── 요청 반영률 ──
    req_total = 0
    req_fulfilled = 0
    for r in schedule.requests:
        if r.is_hard:
            continue  # 확정 요청은 반영률에서 제외
        req_total += 1
        actual = schedule.get_shift(r.nurse_id, r.day)
        if r.shift_type and actual == r.shift_type:
            req_fulfilled += 1
    req_rate = req_fulfilled / req_total if req_total > 0 else 1.0

    # ── D/E/N 편차 ──
    d_counts = [shift_stats[n.id]["D"] for n in nurses]
    e_counts = [shift_stats[n.id]["E"] for n in nurses]
    n_counts = [shift_stats[n.id]["N"] for n in nurses]
    d_dev = (max(d_counts) - min(d_counts)) if d_counts else 0
    e_dev = (max(e_counts) - min(e_counts)) if e_counts else 0
    n_dev = (max(n_counts) - min(n_counts)) if n_counts else 0

    # ── 종합 점수 (100점 만점) ──
    score = 100.0
    # 편차 감점 (편차 1당 -3점, 최대 -30)
    shift_penalty = min((d_dev + e_dev + n_dev) * 3, 30)
    score -= shift_penalty
    # 야간 편차 감점 (편차 1당 -5점, 최대 -20)
    score -= min(night_deviation * 5, 20)
    # 주말 편차 감점
    score -= min(weekend_deviation * 4, 15)
    # 기피 패턴 감점 (건당 -5)
    pattern_count = sum(bad_patterns.values())
    score -= min(pattern_count * 5, 20)
    # 요청 미반영 감점
    score -= (1 - req_rate) * 15
    score = max(0, score)

    # 등급
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
        "score": round(score, 1),
        "shift_stats": shift_stats,
        "night_deviation": night_deviation,
        "weekend_deviation": weekend_deviation,
        "bad_patterns": bad_patterns,
        "request_fulfilled": {
            "total": req_total,
            "fulfilled": req_fulfilled,
            "rate": round(req_rate * 100, 1),
        },
        "d_deviation": d_dev,
        "e_deviation": e_dev,
        "n_deviation": n_dev,
    }
