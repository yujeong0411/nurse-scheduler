"""데이터 모델 정의 — 응급실 간호사 근무표

근무 3종: D, E, N
# 중간근무 확장 시: D, D9, D1, 중1, 중2, E, N (7종)
# D=주간, M(D9/D1/중1/중2)=중간, E=저녁, N=야간
휴무 11종: 주, OFF, POFF, 법휴, 수면, 생휴, 휴가, 특휴, 공가, 경가, 보수
"""
from dataclasses import dataclass, field
from typing import Optional
import json
import os
import calendar


# ══════════════════════════════════════════
# 상수 정의
# ══════════════════════════════════════════

# 근무 코드
WORK_SHIFTS = ["D", "E", "N"]  # "D9", "D1", "중1", "중2" 추후 추가
# WORK_SHIFTS = ["D", "D9", "D1", "중1", "중2", "E", "N"]  # 중간근무 포함 시

# 휴무 코드
OFF_TYPES = ["주", "OFF", "POFF", "법휴", "수면", "생휴", "휴가", "특휴", "공가", "경가", "보수"]

# 전체 코드 (근무 + 휴무)
ALL_CODES = WORK_SHIFTS + OFF_TYPES

# 사용자 신청 휴무 (엑셀에서 읽어오는 것들)
USER_REQUEST_CODES = WORK_SHIFTS + ["OFF", "법휴", "휴가", "특휴", "공가", "경가", "보수", "D 제외", "N 제외", "E 제외"]

# 자동 발생 휴무 (솔버가 배정)
AUTO_OFF_CODES = ["주", "OFF", "POFF", "수면", "생휴"]

# 휴무 배정 우선순위 (솔버가 이 순서로 배정)
# 주휴/OFF 먼저 → 생/수면 그 다음
OFF_PRIORITY = ["주", "OFF", "생휴", "수면", "POFF", "공가", "경가"]

# 수면 계산용 2개월 페어(고정)
# 1-2월, 3-4월, 5-6월, 7-8월, 9-10월, 11-12월
SLEEP_PAIRS = [(1,2), (3,4), (5,6), (7,8), (9,10), (11,12)]

def get_sleep_partner_month(month: int) -> int | None:
    """수면 계산용 파트너 월 반환
    1-2월, 3-4월, 5-6월, 7-8월, 9-10월, 11-12월 고정 페어
    홀수월 = 페어 첫 달 → 파트너 없음 (아직 모름)
    짝수월 = 페어 둘째 달 → 전월이 파트너
    """
    if month % 2 == 0:
        return month - 1
    return None

def get_sleep_pair(month: int) -> tuple[int, int]:
    """해당 월이 속한 수면 계산 페어 반환"""
    for pair in SLEEP_PAIRS:
        if month in pair:
            return pair
    return (month, month)

def is_pair_first_month(month: int) -> bool:
    """페어의 첫 번째 월인가? (홀수월: 1,3,5,7,9,11)"""
    pair = get_sleep_pair(month)
    return month == pair[0]

def sleep_expires_month(month: int) -> int:
    """수면 발생 월 기준, 만료 월 (페어의 둘째 달 말)
    ex) 3월 발생 → 4월 말 만료, 4월 발생 → 4월 말 만료
    """
    _, second = get_sleep_pair(month)
    return second

# 근무 순서 레벨 (역순 금지: 높은 → 낮은 불가)
# D → E → N  (중간근무 추가 시: D → M → E → N)
SHIFT_ORDER = {
    "D": 1,
    # "D9": 2, "D1": 2, "중1": 2, "중2": 2,  # 중간 계열 (M)
    "E": 2,   # → 3 when 중간근무 추가
    "N": 3,   # → 4 when 중간근무 추가
}

# 역할(비고1) 목록
ROLES = ["", "책임만", "외상", "혼자 관찰불가", "혼자 관찰", "급성구역", "준급성", "격리구역"]

# 직급(비고2) 목록
GRADES = ["", "책임", "서브차지"]

# 역할별 동시 근무 제한 (누적 구조)
# 각 티어: (해당 역할 집합, D 최대, E 최대, N 최대)
ROLE_TIERS = [
    ({"책임만"}, 1, 1, 1),
    ({"외상"}, 1, 1, 1),
    ({"외상", "혼자 관찰불가"}, 1, 2, 1),
    ({"외상", "혼자 관찰불가", "혼자 관찰"}, 2, 2, 2),
    ({"외상", "혼자 관찰불가", "혼자 관찰", "준급성", "급성구역"}, 3, 3, 3),
    ({"외상", "혼자 관찰불가", "혼자 관찰", "준급성", "급성구역", "격리구역"}, 4, 4, 4),
]


# ══════════════════════════════════════════
# 데이터 클래스
# ══════════════════════════════════════════

# @dataclass 사용 시 __init__이 자동 생성
@dataclass
class Nurse:
    """간호사"""
    id: int
    name: str

    # 비교1 : 역할/구역
    role: str = ""                  # "책임만","외상","혼자 관찰","혼자 관찰불가","급성구역","준급성","소아",""
    
    # 비고2: 직급
    grade: str = ""                 # "책임","서브차지",""

    # 비고3: 특수 조건
    is_pregnant:bool = False    # 임산부 → 4근무당 POFF 1개
    is_male: bool = False       # 남자 → 생리휴무 제외

    # 비고4: 근무 형태
    is_4day_week: bool = False  # 주4일제 → 주당 OFF 2개

    # 고정 주휴 요일 (0=월, 1=화, ..., 6=일), None이면 미지정
    fixed_weekly_off: Optional[int] = None

    # 휴가/수면 관련
    vacation_days: int = 0       # 잔여 휴가 일수
    prev_month_N: int = 0        # 전월 N 횟수 (짝수월에서만 사용: 수면 2개월 합산용)
    pending_sleep: bool = False  # 전월(홀수월)에서 발생한 미사용 수면 (짝수월에서만 유효)
    menstrual_used: bool = False # 이번달 생휴 이미 사용 여부

    note: str = ""

    def to_dict(self):
        """저장용"""
        return {
            "id": self.id,
            "name": self.name,
            "role": self.role, 
            "grade": self.grade,
            "is_pregnant": self.is_pregnant, 
            "is_male": self.is_male,
            "is_4day_week": self.is_4day_week,
            "fixed_weekly_off": self.fixed_weekly_off,
            "vacation_days": self.vacation_days,
            "prev_month_N": self.prev_month_N,
            "pending_sleep": self.pending_sleep,
            "menstrual_used": self.menstrual_used,
            "note": self.note,
        }

    # @classmethod : 객체 없이 클래스에서 직접 호출
    @classmethod
    def from_dict(cls, d):
        """복원용"""
        valid = {"id", "name", "role", "grade", "is_pregnant", "is_male",
                 "is_4day_week", "fixed_weekly_off",  "vacation_days", "prev_month_N", "pending_sleep",  "menstrual_used", "note"}
        filtered = {k: v for k, v in d.items() if k in valid}
        return cls(**filtered)


@dataclass
class Request:
    """개인 요청 1건

    code 종류:
      근무 희망: D, E, N, (D9, D1, 중1, 중2)
      휴무 확정: 법휴, 휴, 특휴, 공, 경
      휴무 희망: OFF
      제외 요청: D 제외, E 제외, N 제외
      자동 발생: 주, 수면, 생, POFF (솔버가 배정)
    """
    nurse_id: int                   # 어느 간호사가
    day: int                        # 며칠에 (1~31)
    code: str                       # 뭘 원하는지 

    def __post_init__(self):
        self.code = self.code.strip()  # 공백 제거
        # "D제외" → "D 제외", "N제외" → "N 제외" 등 통일
        for s in ["D", "E", "N"]:
            if self.code.replace(" ", "") == f"{s}제외":
                self.code = f"{s} 제외"
                break
        # "수면(1,2월)", "수면(2월)", "수면 (3,4월)" 등 → "수면"
        if self.code.startswith("수면"):
            self.code = "수면"

    # @property : 함수인데 변수처럼 -> 사용할 때 ()가 필요 없음 request.is_hard  
    @property
    def is_hard(self) -> bool:
        """반드시 지켜야 하는 확정 요청인가?"""
        return self.code in ("주", "법휴", "휴가", "특휴", "생휴", "수면", "공가", "경가", "보수")   # "OFF"는 소프트(S1)로 처리 — H11이 주당 2개 보장

    @property
    def is_exclude(self) -> bool:
        """특정 근무 제외 요청인가?"""
        return "제외" in self.code

    @property
    def excluded_shift(self) -> Optional[str]:
        """제외 요청인 경우 제외할 근무 타입"""
        if self.code == "D 제외":
            return "D"
        elif self.code == "E 제외":
            return "E"
        elif self.code == "N 제외":
            return "N"
        return None

    @property
    def is_work_request(self) -> bool:
        """근무 희망 요청인가?"""
        return self.code in WORK_SHIFTS

    @property
    def is_off_request(self) -> bool:
        """휴무 관련 요청인가?"""
        return self.code in OFF_TYPES or self.code == "OFF"

    def to_dict(self):
        return {"nurse_id": self.nurse_id, "day": self.day, "code": self.code}

    @classmethod
    def from_dict(cls, d):
        return cls(**d)

@dataclass
class Rules:
    """근무표 규칙"""

    # ── 일일 인원 ──
    daily_D: int = 7            # D 근무 인원
    daily_E: int = 8            # E 근무 인원
    daily_N: int = 7            # N 근무 인원

    # ── 야간(N) 제한 ──
    max_N_per_month: int = 6    # 월 N 최대 횟수
    max_consecutive_N: int = 3  # 연속 N 최대
    off_after_2N: int = 2       # N 2연속 후 필요한 휴무 수

    # ── 연속 근무 ──
    max_consecutive_work: int = 5   # 최대 연속 근무일

    # ── 주당 휴무 ──
    min_weekly_off: int = 2         # 주당 최소 휴무 수

    # ── 근무 순서 ──
    ban_reverse_order: bool = True  # D→중간→E→N 역순 금지

    # ── 직급 요구 ──
    min_chief_per_shift: int = 1        # 책임 최소 (매 근무)
    min_senior_per_shift: int = 2       # 책임+서브차지 최소 (매 근무)
    max_junior_per_shift: int = 3       # 일반(빈칸) 최대 (매 근무, 권고)

    # ── 특수 휴무 ──
    pregnant_poff_interval: int = 4     # 임산부: N근무당 POFF (4근무마다 1개)
    menstrual_leave: bool = True        # 생리휴무 (남자 제외 월 1개)

    # ── 수면 발생 조건 ──
    sleep_N_monthly: int = 7            # 1개월 N >= 이 값이면 수면 발생
    sleep_N_bimonthly: int = 11         # 2개월 합산 N >= 이 값이면 수면 발생

    # ── 법정공휴일 ──
    public_holidays: list = field(default_factory=list)    # 해당 월 공휴일 날짜 [1, 15, ...]

    def get_daily_staff(self, shift: str) -> int:
        """근무별 일일 필요 인원"""
        return {"D": self.daily_D, "E": self.daily_E, "N": self.daily_N}.get(shift, 0)

    def to_dict(self):
        return {k: v for k, v in self.__dict__.items()}

    @classmethod
    def from_dict(cls, d):
        valid = {f.name for f in __import__('dataclasses').fields(cls)}
        filtered = {k: v for k, v in d.items() if k in valid}
        return cls(**filtered)


@dataclass
class Schedule:
    """
    생성된 근무표 결과
    
    solver가 결과를 여기에 채우고, result_tab이 이걸 읽어서 화면에 노출
    """
    year: int
    month: int
    nurses: list                # list[Nurse]
    rules: Rules
    requests: list              # list[Request]
    # 결과: schedule_data[nurse_id][day] = "D"/"E"/"N"/"OFF"/"주"/...
    schedule_data: dict = field(default_factory=dict)   # 객체를 만들때 마다 dict()를 새로 호출해서 빈 딕셔너리 생성

    @property
    def num_days(self) -> int:
        return calendar.monthrange(self.year, self.month)[1]

    def is_weekend(self, day: int) -> bool:
        """주말 여부"""
        return calendar.weekday(self.year, self.month, day) >= 5   # 토=5, 일=6

    def weekday_index(self, day: int) -> int:
        """0=월, 1=화, ..., 6=일"""
        return calendar.weekday(self.year, self.month, day)

    def weekday_name(self, day: int) -> str:
        """요일 구분"""
        names = ["월", "화", "수", "목", "금", "토", "일"]
        return names[self.weekday_index(day)]

    def get_shift(self, nurse_id: int, day: int) -> str:
        """해당 간호사의 해당 날짜의 근무가 뭔지"""
        return self.schedule_data.get(nurse_id, {}).get(day, "")

    def set_shift(self, nurse_id: int, day: int, shift: str):
        """해당 간호사의 해당 날짜의 근무 변경"""
        if nurse_id not in self.schedule_data:
            self.schedule_data[nurse_id] = {}
        self.schedule_data[nurse_id][day] = shift

    def get_day_count(self, nurse_id: int, shift: str) -> int:
        """특정 간호사의 특정 근무/휴무 횟수"""
        if nurse_id not in self.schedule_data:
            return 0
        return sum(1 for s in self.schedule_data[nurse_id].values() if s == shift)

    def get_work_count(self, nurse_id: int) -> int:
        """특정 간호사의 총 근무일 수 (근무만, 휴무 제외)"""
        if nurse_id not in self.schedule_data:
            return 0
        return sum(1 for s in self.schedule_data[nurse_id].values() if s in WORK_SHIFTS)

    def get_staff_count(self, day: int, shift: str) -> int:
        """특정 날짜의 특정 근무 배정 인원 수"""
        count = 0
        for nid in self.schedule_data:
            if self.schedule_data[nid].get(day) == shift:
                count += 1
        return count

    def get_staff_by_shift(self, day: int, shift: str) -> list[int]:
        """특정 날짜의 특정 근무에 배정된 간호사 ID 목록"""
        return [nid for nid in self.schedule_data
                if self.schedule_data[nid].get(day) == shift]

    def is_work(self, nurse_id: int, day: int) -> bool:
        """해당 날짜가 근무인가?"""
        return self.get_shift(nurse_id, day) in WORK_SHIFTS

    def is_off(self, nurse_id: int, day: int) -> bool:
        """해당 날짜가 휴무인가?"""
        s = self.get_shift(nurse_id, day)
        return s in OFF_TYPES or s == ""

    def get_week_ranges(self) -> list[tuple[int, int]]:
        """월의 주 단위 범위 반환: [(1,7), (8,14), ...]
        고정 주기: 1~7일=1주, 8~14일=2주, ...
        """
        weeks = []
        d = 1
        while d <= self.num_days:
            end = min(d + 6, self.num_days)
            weeks.append((d, end))
            d = end + 1
        return weeks


class DataManager:
    """JSON 저장/불러오기 관리"""

    def __init__(self):
        self.data_dir = self._get_data_dir()
        os.makedirs(self.data_dir, exist_ok=True)

    def _get_data_dir(self):
        # exe와 같은 폴더의 data/ 디렉토리
        if getattr(os.sys, 'frozen', False):  # os.sys.frozen 은 PyInstaller 등으로 패키징된 실행파일(exe) 에서만 존재하는 속성
            base = os.path.dirname(os.sys.executable)  # 현재 실행 중인 exe 파일 경로
        else:
            base = os.path.dirname(os.path.abspath(__file__))  # 현재 파일의 절대경로
            base = os.path.dirname(base)  # 상위 폴더로 올라감 : engine/ 상위
        return os.path.join(base, "data")

    def _backup_dir(self):
        """백업 폴더 : usb 분실 대비"""
        docs = os.path.expanduser("~/Documents/NurseScheduler_backup")
        os.makedirs(docs, exist_ok=True)
        return docs
    
    def _save_json(self, filename, data, backup=True):
        path = os.path.join(self.data_dir, filename)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        if backup:
            backup_path = os.path.join(self._backup_dir(), filename)
            with open(backup_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

    def _load_json(self, filename, default=None):
        path = os.path.join(self.data_dir, filename)
        if not os.path.exists(path):
            return default
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def save_nurses(self, nurses: list):
        self._save_json("nurses.json", [n.to_dict() for n in nurses])

    def load_nurses(self) -> list:
        data = self._load_json("nurses.json", [])
        return [Nurse.from_dict(d) for d in data]

    def save_rules(self, rules: Rules):
        self._save_json("rules.json", rules.to_dict())

    def load_rules(self) -> Rules:
        data = self._load_json("rules.json")
        return Rules.from_dict(data) if data else Rules()

    def save_requests(self, requests: list, year: int, month: int):
        self._save_json(
            f"requests_{year}_{month:02d}.json",
            [r.to_dict() for r in requests],
            backup=False,
        )

    def load_requests(self, year: int, month: int) -> list:
        data = self._load_json(f"requests_{year}_{month:02d}.json", [])
        return [Request.from_dict(d) for d in data]

    def save_schedule(self, schedule_data: dict, year: int, month: int):
        converted = {}
        for nid, days in schedule_data.items():
            converted[str(nid)] = {str(d): s for d, s in days.items()}
        self._save_json(f"schedule_{year}_{month:02d}.json", converted)

    def load_schedule(self, year: int, month: int) -> dict:
        raw = self._load_json(f"schedule_{year}_{month:02d}.json", {})
        return {int(nid): {int(d): s for d, s in days.items()}
                for nid, days in raw.items()}