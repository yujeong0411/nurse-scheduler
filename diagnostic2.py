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

def weekday_of(di):
    return (start_date + timedelta(days=di)).weekday()

nurse_span = {}
for ni, nurse in enumerate(nurses):
    sick = sorted(r.day-1 for r in requests if r.nurse_id==nurse.id and r.is_hard and r.code=='병가' and 0<=r.day-1<num_days)
    nurse_span[ni] = (sick[0],sick[-1]) if sick else None

def in_span(ni, di):
    s = nurse_span[ni]
    return s is not None and s[0] <= di <= s[1]

four_day_nis = [ni for ni,n in enumerate(nurses) if n.is_4day_week]
print("주4일제 간호사:", [(ni, nurses[ni].name) for ni in four_day_nis])
print()

# 각 4일제 간호사를 제외하고 테스트
for exclude_ni in four_day_nis:
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
        required = 2 if (nurses[ni].is_4day_week and ni != exclude_ni) else 1
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
    status = solver.solve(model)
    print(f"제외 ni={exclude_ni} ({nurses[exclude_ni].name}): {solver.status_name(status)}")
