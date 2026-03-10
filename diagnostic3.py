from engine.models import DataManager
from engine.solver import _주, _OFF, _병가, NUM_TYPES, NAME_TO_IDX
from ortools.sat.python import cp_model
from datetime import date, timedelta

dm = DataManager()
nurses = dm.load_nurses()
settings = dm.load_settings()
start_date = date.fromisoformat(settings['start_date'])
requests = dm.load_requests(settings['start_date'])
rules = dm.load_rules()

num_days = 35
num_nurses = len(nurses)
nurse_idx = {n.id: i for i, n in enumerate(nurses)}
four_day_nis = [ni for ni,n in enumerate(nurses) if n.is_4day_week]

def weekday_of(di):
    return (start_date + timedelta(days=di)).weekday()

nurse_span = {}
for ni, nurse in enumerate(nurses):
    sick = sorted(r.day-1 for r in requests if r.nurse_id==nurse.id and r.is_hard and r.code=='병가' and 0<=r.day-1<num_days)
    nurse_span[ni] = (sick[0],sick[-1]) if sick else None

def in_span(ni, di):
    s = nurse_span[ni]
    return s is not None and s[0] <= di <= s[1]

def test_with_required(required_map):
    """required_map: {ni: required_off_count} - 미지정은 1"""
    model = cp_model.CpModel()
    shifts = {(ni,di,si): model.new_bool_var(f's_{ni}_{di}_{si}')
              for ni in range(num_nurses) for di in range(num_days) for si in range(NUM_TYPES)}
    for ni in range(num_nurses):
        for di in range(num_days):
            model.add(sum(shifts[(ni,di,si)] for si in range(NUM_TYPES)) == 1)
    for r in requests:
        if not r.is_hard or r.nurse_id not in nurse_idx: continue
        ni = nurse_idx[r.nurse_id]; di = r.day - 1
        if di < 0 or di >= num_days: continue
        if r.code == '주' and in_span(ni, di): continue
        if r.code in NAME_TO_IDX:
            model.add(shifts[(ni,di,NAME_TO_IDX[r.code])] == 1)
    for ni, nurse in enumerate(nurses):
        if nurse.fixed_weekly_off is not None:
            for di in range(num_days):
                if weekday_of(di) == nurse.fixed_weekly_off:
                    if in_span(ni, di):
                        model.add(shifts[(ni,di,_주)]==0); model.add(shifts[(ni,di,_병가)]==1)
                    else: model.add(shifts[(ni,di,_주)]==1)
                else: model.add(shifts[(ni,di,_주)]==0)
        else:
            for di in range(num_days):
                model.add(shifts[(ni,di,_주)]==0)
    for ni in range(num_nurses):
        required = required_map.get(ni, 1)
        nurse_fwo = nurses[ni].fixed_weekly_off
        for w in range(0, num_days, 7):
            w_end = min(w+7, num_days)
            off_sum = sum(shifts[(ni,di,_OFF)] for di in range(w, w_end))
            if w_end - w < 4:
                model.add(off_sum <= required); continue
            all_in = all(in_span(ni,di) for di in range(w, w_end))
            if all_in: model.add(off_sum <= required)
            elif any(in_span(ni,di) for di in range(w, w_end)):
                avail = sum(1 for di in range(w,w_end)
                            if not in_span(ni,di)
                            and not (nurse_fwo is not None and weekday_of(di)==nurse_fwo))
                model.add(off_sum == min(required, avail))
            else: model.add(off_sum == required)
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 20
    return solver.status_name(solver.solve(model))

# 각 4일제 간호사 단독으로 2 OFFs 테스트
print("=== 단독 2 OFFs 테스트 ===")
for ni in four_day_nis:
    result = test_with_required({ni: 2})
    print(f"  ni={ni} only 2 OFFs: {result}")

print()

# 각 주차별로 ni=6의 OFF 요구사항 분석
print("=== ni=6 주차별 분석 ===")
ni6 = 6
nurse6 = nurses[ni6]
sp = nurse_span[ni6]
fwo = nurse6.fixed_weekly_off
print(f"fixed_weekly_off={fwo} (weekday), 병가 span={sp}")
for w in range(0, num_days, 7):
    w_end = min(w+7, num_days)
    days_info = []
    for di in range(w, w_end):
        d = start_date + timedelta(days=di)
        is_sick = in_span(ni6, di)
        is_fixed = fwo is not None and weekday_of(di) == fwo
        hard = [r.code for r in requests if r.nurse_id==nurse6.id and r.day==di+1 and r.is_hard]
        days_info.append(f"di={di}({d.strftime('%a')}{'[병가]' if is_sick else ''}{'[주]' if is_fixed else ''}{hard})")
    all_in = sp and all(sp[0]<=di<=sp[1] for di in range(w,w_end))
    any_in = sp and any(sp[0]<=di<=sp[1] for di in range(w,w_end))
    avail = sum(1 for di in range(w,w_end) if not in_span(ni6,di) and not (fwo is not None and weekday_of(di)==fwo))
    req = min(2, avail) if any_in and not all_in else (0 if all_in else 2)
    print(f"Week{w//7}: req_off={req}, avail={avail}")
    for d in days_info:
        print(f"  {d}")
