"""데이터 모델 정의"""
from dataclasses import dataclass, field
from typing import Optional
import json
import os
import calendar

# @dataclass 사용 시 __init__이 자동 생성
@dataclass
class Nurse:
    id: int
    name: str
    skill_level: int = 2            # 1=신규, 2=일반, 3=주임, 4=책임
    can_day: bool = True            # day 가능?
    can_evening: bool = True        # evening 가능?
    can_night: bool = True          # Night 가능? (False=야간 금지)
    fixed_shift: Optional[str] = None  # "D"/"E"/"N" = 매일 고정 -> "D" = 매일 Day만
    preceptor_of: Optional[int] = None # 프리셉팅 대상 간호사 ID
    weekday_only: bool = False         # True = 주말 근무 안함
    note: str = ""

    def to_dict(self):
        """저장용"""
        return {
            "id": self.id, "name": self.name,
            "skill_level": self.skill_level,
            "can_day": self.can_day, 
            "can_evening": self.can_evening,
            "can_night": self.can_night, 
            "fixed_shift": self.fixed_shift,
            "preceptor_of": self.preceptor_of, 
            "weekday_only": self.weekday_only,
            "note": self.note,
        }

    # @classmethod : 객체 없이 클래스에서 직접 호출
    @classmethod
    def from_dict(cls, d):
        """복원용"""
        d.setdefault("weekday_only", False)
        return cls(**d)


@dataclass
class Request:
    """개인 요구사항"""
    nurse_id: int                   # 어느 간호사가
    day: int                        # 며칠에 (1~31)
    code: str                       # 뭘 원하는지 : "OFF","연차","D","E","N","D!","E!","N!"

    # @property : 함수인데 변수처럼 -> 사용할 때 ()가 필요 없음 request.is_hard  
    @property
    def is_hard(self) -> bool:
        """True면 Hard, False면 Soft"""
        return self.code in ("연차", "D!", "E!", "N!")

    @property
    def shift_type(self) -> Optional[str]:
        """evaluator.py에서 요청 반영률 계산할 때 사용"""
        mapping = {
            "D": "D", "E": "E", "N": "N",
            "D!": "D", "E!": "E", "N!": "N",
            "OFF": "OFF", "연차": "OFF",
        }
        return mapping.get(self.code)

    def to_dict(self):
        return {"nurse_id": self.nurse_id, "day": self.day, "code": self.code}

    @classmethod
    def from_dict(cls, d):
        return cls(**d)


@dataclass
class Rules:
    # 평일 인원 배치
    weekday_min_day: int = 5            
    weekday_min_evening: int = 5
    weekday_min_night: int = 2
    # 주말 인원 배치
    weekend_min_day: int = 4
    weekend_min_evening: int = 4
    weekend_min_night: int = 2

    # 금지 패턴
    ban_night_to_day: bool = True     # N→D
    ban_night_to_evening: bool = True # N→E
    ban_evening_to_day: bool = True   # E→D

    # 연속 제한
    max_consecutive_work: int = 5     # 최대 연속 근무일
    max_consecutive_night: int = 3    # 최대 나이트 근무일
    night_off_after: int = 1          # 야간 연속 후 OFF 일수

    # 휴무
    min_monthly_off: int = 8          # 최소 월 휴무일
    max_monthly_off: int = 20         # 최대 월 휴무일
    max_consecutive_off: int = 5      # 최대 연속 휴무일

    # 팀 구성
    senior_required_all: bool = True   # 모든 근무(D/E/N)에 숙련자 필수
    ban_newbie_pair_night: bool = True    # 신규끼리 야간 금지

    def get_min_staff(self, shift: str, is_weekend: bool) -> int:
        """각 근무별로 최소 인원 수 반환"""
        if is_weekend:  # 주말
            return {"D": self.weekend_min_day, "E": self.weekend_min_evening,
                    "N": self.weekend_min_night}[shift]
        else:  # 평일
            return {"D": self.weekday_min_day, "E": self.weekday_min_evening,
                    "N": self.weekday_min_night}[shift]

    def to_dict(self):
        return {k: v for k, v in self.__dict__.items()}

    @classmethod
    def from_dict(cls, d):
        return cls(**d)


@dataclass
class Schedule:
    """
    생성된 근무표 결과
    
    solver가 결과를 여기에 채우고, result_tab이 이걸 읽어서 화면에 노출
    """
    year: int
    month: int
    nurses: list  # list of Nurse
    rules: Rules
    requests: list  # list of Request
    # 결과: schedule_data[nurse_id][day] = "D"/"E"/"N"/"OFF"
    schedule_data: dict = field(default_factory=dict)   # 객체를 만들때 마다 dict()를 새로 호출해서 빈 딕셔너리 생성

    @property
    def num_days(self) -> int:
        return calendar.monthrange(self.year, self.month)[1]

    def is_weekend(self, day: int) -> bool:
        """주말 여부"""
        wd = calendar.weekday(self.year, self.month, day)
        return wd >= 5  # 토=5, 일=6

    def weekday_name(self, day: int) -> str:
        """요일 구분"""
        names = ["월", "화", "수", "목", "금", "토", "일"]
        wd = calendar.weekday(self.year, self.month, day)
        return names[wd]

    def get_shift(self, nurse_id: int, day: int) -> str:
        """해당 간호사의 해당 날짜의 근무가 뭔지"""
        return self.schedule_data.get(nurse_id, {}).get(day, "")

    def set_shift(self, nurse_id: int, day: int, shift: str):
        """해당 간호사의 해당 날짜의 근무 변경"""
        if nurse_id not in self.schedule_data:
            self.schedule_data[nurse_id] = {}
        self.schedule_data[nurse_id][day] = shift

    def get_day_count(self, nurse_id: int, shift: str) -> int:
        """해당 간호사의 이번 달 해당 근무의 횟수"""
        if nurse_id not in self.schedule_data:
            return 0
        return sum(1 for s in self.schedule_data[nurse_id].values() if s == shift)

    def get_staff_count(self, day: int, shift: str) -> int:
        """해당 날짜의 해당 근무의 총 인원 수"""
        count = 0
        for nid in self.schedule_data:
            if self.schedule_data[nid].get(day) == shift:
                count += 1
        return count


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

    def save_nurses(self, nurses: list):
        path = os.path.join(self.data_dir, "nurses.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump([n.to_dict() for n in nurses], f, ensure_ascii=False, indent=2)
        # 백업
        backup = os.path.join(self._backup_dir(), "nurses.json")
        with open(backup, "w", encoding="utf-8") as f:
            json.dump([n.to_dict() for n in nurses], f, ensure_ascii=False, indent=2)

    def load_nurses(self) -> list:
        path = os.path.join(self.data_dir, "nurses.json")
        if not os.path.exists(path):
            return []
        with open(path, "r", encoding="utf-8") as f:
            return [Nurse.from_dict(d) for d in json.load(f)]

    def save_rules(self, rules: Rules):
        path = os.path.join(self.data_dir, "rules.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(rules.to_dict(), f, ensure_ascii=False, indent=2)
        backup = os.path.join(self._backup_dir(), "rules.json")
        with open(backup, "w", encoding="utf-8") as f:
            json.dump(rules.to_dict(), f, ensure_ascii=False, indent=2)

    def load_rules(self) -> Rules:
        path = os.path.join(self.data_dir, "rules.json")
        if not os.path.exists(path):
            return Rules()
        with open(path, "r", encoding="utf-8") as f:
            return Rules.from_dict(json.load(f))

    def save_requests(self, requests: list, year: int, month: int):
        path = os.path.join(self.data_dir, f"requests_{year}_{month:02d}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump([r.to_dict() for r in requests], f, ensure_ascii=False, indent=2)

    def load_requests(self, year: int, month: int) -> list:
        path = os.path.join(self.data_dir, f"requests_{year}_{month:02d}.json")
        if not os.path.exists(path):
            return []
        with open(path, "r", encoding="utf-8") as f:
            return [Request.from_dict(d) for d in json.load(f)]

    def save_schedule(self, schedule_data: dict, year: int, month: int):
        path = os.path.join(self.data_dir, f"schedule_{year}_{month:02d}.json")
        # key를 str로 변환 (JSON은 int key 불가)
        converted = {}
        for nid, days in schedule_data.items():
            converted[str(nid)] = {str(d): s for d, s in days.items()}  # id, 날짜 모두 str 변환
        with open(path, "w", encoding="utf-8") as f:
            json.dump(converted, f, ensure_ascii=False, indent=2)
        backup = os.path.join(self._backup_dir(), f"schedule_{year}_{month:02d}.json")
        with open(backup, "w", encoding="utf-8") as f:
            json.dump(converted, f, ensure_ascii=False, indent=2)

    def load_schedule(self, year: int, month: int) -> dict:
        path = os.path.join(self.data_dir, f"schedule_{year}_{month:02d}.json")
        if not os.path.exists(path):
            return {}
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        # key를 int로 복원
        return {int(nid): {int(d): s for d, s in days.items()} for nid, days in raw.items()}
