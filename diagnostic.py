from engine.models import DataManager, ROLE_TIERS
from engine.solver import (
    _D,_E,_N,_중2,_주,_OFF,_병가,_생휴,_수면,_휴가,_특휴,_공가,_경가,_보수,_필수,_번표,_POFF,
    NUM_TYPES,NAME_TO_IDX,ALL_OFF,WORK_INDICES,M_FAMILY,D_FAMILY,E_FAMILY,FORBIDDEN_PAIRS,SHIFT_LEVEL
)
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

# 병가 span
nurse_span = {}
for ni, nurse in enumerate(nurses):
    sick = sorted(r.day-1 for r in requests if r.nurse_id==nurse.id and r.is_hard and r.code=='병가' and 0<=r.day-1<num_days)
    nurse_span[ni] = (sick[0],sick[-1]) if sick else None

def in_span(ni, di):
    s = nurse_span[ni]
    return s is not None and s[0] <= di <= s[1]

def build(h11_4day=False, h2=False, h3=False, h4=False, h6=False, h12=False, h13=False, hard_counts=False, h20=False):
    model = cp_model.CpModel()
    shifts = {(ni,di,si): model.new_bool_var(f's_{ni}_{di}_{si}')
              for ni in range(num_nurses) for di in range(num_days) for si in range(NUM_TYPES)}
    # H1
    for ni in range(num_nurses):
        for di in range(num_days):
            model.add(sum(shifts[(ni,di,si)] for si in range(NUM_TYPES)) == 1)
    # fixed_off_days
    fixed_off_days = set()
    for ni, nurse in enumerate(nurses):
        if nurse.fixed_weekly_off is not None:
            for di in range(num_days):
                if weekday_of(di) == nurse.fixed_weekly_off:
                    fixed_off_days.add((ni,di))
    # H8
    req_hard_days = set()
    for r in requests:
        if not r.is_hard or r.nurse_id not in nurse_idx: continue
        ni = nurse_idx[r.nurse_id]; di = r.day - 1
        if di < 0 or di >= num_days: continue
        if r.code == '주' and in_span(ni, di): continue
        req_hard_days.add((ni,di))
        if r.code in NAME_TO_IDX:
            model.add(shifts[(ni,di,NAME_TO_IDX[r.code])] == 1)
    # H10/H10a
    for ni, nurse in enumerate(nurses):
        if nurse.fixed_weekly_off is not None:
            for di in range(num_days):
                if weekday_of(di) == nurse.fixed_weekly_off:
                    if in_span(ni, di):
                        model.add(shifts[(ni,di,_주)] == 0)
                        model.add(shifts[(ni,di,_병가)] == 1)
                    else:
                        model.add(shifts[(ni,di,_주)] == 1)
                else:
                    model.add(shifts[(ni,di,_주)] == 0)
    for ni, nurse in enumerate(nurses):
        for di in range(num_days):
            if nurse.fixed_weekly_off is None or weekday_of(di) != nurse.fixed_weekly_off:
                model.add(shifts[(ni,di,_주)] == 0)
    # H11
    for ni in range(num_nurses):
        required = 2 if (h11_4day and nurses[ni].is_4day_week) else 1
        nurse_fwo = nurses[ni].fixed_weekly_off
        for w in range(0, num_days, 7):
            w_end = min(w+7, num_days)
            off_sum = sum(shifts[(ni,di,_OFF)] for di in range(w, w_end))
            if w_end - w < 4:
                model.add(off_sum <= required)
                continue
            all_in = all(in_span(ni,di) for di in range(w, w_end))
            if all_in:
                model.add(off_sum <= required)
            elif any(in_span(ni,di) for di in range(w, w_end)):
                avail = sum(1 for di in range(w,w_end)
                            if not in_span(ni,di)
                            and not (nurse_fwo is not None and weekday_of(di)==nurse_fwo))
                model.add(off_sum == min(required, avail))
            else:
                model.add(off_sum == required)
    if h2:
        중2_nurses = [ni for ni,n in enumerate(nurses) if n.role=='중2']
        non중2 = [ni for ni,n in enumerate(nurses) if n.role!='중2']
        for di in range(num_days):
            model.add(sum(shifts[(ni,di,_D)] for ni in range(num_nurses))==rules.daily_D)
            model.add(sum(shifts[(ni,di,_E)] for ni in range(num_nurses))==rules.daily_E)
            model.add(sum(shifts[(ni,di,_N)] for ni in range(num_nurses))==rules.daily_N)
            if 중2_nurses and weekday_of(di)<5:
                model.add(sum(shifts[(ni,di,_중2)] for ni in 중2_nurses)==rules.daily_M)
            else:
                model.add(sum(shifts[(ni,di,si)] for ni in range(num_nurses) for si in M_FAMILY)==0)
        for ni in non중2:
            for di in range(num_days):
                for si in M_FAMILY: model.add(shifts[(ni,di,si)]==0)
    if h3:
        for ni in range(num_nurses):
            for di in range(num_days-1):
                for si,sj in FORBIDDEN_PAIRS:
                    model.add(shifts[(ni,di,si)]+shifts[(ni,di+1,sj)]<=1)
            for di in range(num_days-2):
                model.add(shifts[(ni,di,_N)]+shifts[(ni,di+2,_D)]<=1)
    if h4:
        for ni in range(num_nurses):
            for di in range(num_days-rules.max_consecutive_work):
                model.add(sum(shifts[(ni,di+dd,oi)] for dd in range(rules.max_consecutive_work+1) for oi in ALL_OFF)>=1)
    if h6:
        for ni in range(num_nurses):
            for di in range(num_days-1):
                for k in range(rules.off_after_2N):
                    if di+2+k < num_days:
                        model.add(shifts[(ni,di,_N)]+shifts[(ni,di+1,_N)]-1 <= sum(shifts[(ni,di+2+k,oi)] for oi in ALL_OFF))
    if h12:
        chiefs=[ni for ni,n in enumerate(nurses) if n.grade=='책임']
        for di in range(num_days):
            for si in [_D,_E,_N]:
                model.add(sum(shifts[(ni,di,si)] for ni in chiefs)>=rules.min_chief_per_shift)
    if h13:
        seniors=[ni for ni,n in enumerate(nurses) if n.grade in ('책임','서브차지')]
        for di in range(num_days):
            for si in [_D,_E,_N]:
                model.add(sum(shifts[(ni,di,si)] for ni in seniors)>=rules.min_senior_per_shift)
    if hard_counts:
        for ni, nurse in enumerate(nurses):
            hc = {}
            for code, idx in [('생휴',_생휴),('수면',_수면),('휴가',_휴가),('병가',_병가),('특휴',_특휴),('공가',_공가),('경가',_경가),('보수',_보수),('필수',_필수),('번표',_번표)]:
                hc[idx] = sum(1 for r in requests if r.is_hard and r.nurse_id==nurse.id and r.code==code and 1<=r.day<=num_days and (ni,r.day-1) not in fixed_off_days)
            sp = nurse_span[ni]
            if sp:
                hc[_병가] += sum(1 for di in range(num_days) if (ni,di) in fixed_off_days and sp[0]<=di<=sp[1])
            for idx in [_특휴,_공가,_경가,_보수,_필수,_번표,_병가]:
                model.add(sum(shifts[(ni,di,idx)] for di in range(num_days)) == hc[idx])
            model.add(sum(shifts[(ni,di,_생휴)] for di in range(num_days)) == (0 if nurse.is_male else 1))
    if h20:
        중2e = any(n.role=='중2' for n in nurses)
        중2pw = rules.daily_M if 중2e else 0
        nwd = sum(1 for di in range(num_days) if weekday_of(di)<5)
        nwe = num_days - nwd
        tws = nwd*(rules.daily_D+중2pw+rules.daily_E+rules.daily_N) + nwe*(rules.daily_D+rules.daily_E+rules.daily_N)
        tos = num_nurses*num_days - tws
        extra = 5
        fourday = [ni for ni in range(num_nurses) if nurses[ni].is_4day_week]
        regular = [ni for ni in range(num_nurses) if not nurses[ni].is_4day_week]
        base = round((tos - extra*len(fourday)) / max(num_nurses,1))
        def exp_off(ni):
            nid = nurses[ni].id
            hoff = sum(1 for r in requests if r.nurse_id==nid and r.is_hard and 1<=r.day<=num_days)
            req = 2 if nurses[ni].is_4day_week else 1
            sp = nurse_span[ni]
            fwo = nurses[ni].fixed_weekly_off
            for w in range(0,num_days,7):
                we = min(w+7,num_days)
                if we-w<4: continue
                if sp and all(sp[0]<=di<=sp[1] for di in range(w,we)): continue
                if sp and any(sp[0]<=di<=sp[1] for di in range(w,we)):
                    av = sum(1 for di in range(w,we) if not (sp[0]<=di<=sp[1]) and not (fwo is not None and weekday_of(di)==fwo))
                    hoff += min(req,av)
                else:
                    hoff += req
            return hoff
        for ni in regular:
            if exp_off(ni) > base+2: continue
            os = sum(shifts[(ni,di,oi)] for di in range(num_days) for oi in ALL_OFF)
            model.add(os >= base-2); model.add(os <= base+2)
        ft = base + extra
        for ni in fourday:
            if exp_off(ni) > ft+2: continue
            os = sum(shifts[(ni,di,oi)] for di in range(num_days) for oi in ALL_OFF)
            model.add(os >= ft-2); model.add(os <= ft+2)
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 30
    status = solver.solve(model)
    return solver.status_name(status)

print('H1+H8+H10+H11(1):   ', build())
print('H1+H8+H10+H11(2):   ', build(h11_4day=True))
print('+H2:                 ', build(h11_4day=True, h2=True))
print('+H3:                 ', build(h11_4day=True, h2=True, h3=True))
print('+H4:                 ', build(h11_4day=True, h2=True, h3=True, h4=True))
print('+H6:                 ', build(h11_4day=True, h2=True, h3=True, h4=True, h6=True))
print('+H12+H13:            ', build(h11_4day=True, h2=True, h3=True, h4=True, h6=True, h12=True, h13=True))
print('+hard_counts:        ', build(h11_4day=True, h2=True, h3=True, h4=True, h6=True, h12=True, h13=True, hard_counts=True))
print('+H20:                ', build(h11_4day=True, h2=True, h3=True, h4=True, h6=True, h12=True, h13=True, hard_counts=True, h20=True))
