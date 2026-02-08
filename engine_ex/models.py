"""데이터 모델 정의"""
from dataclasses import dataclass, field
from typing import Optional
import json
import os
import calendar


@dataclass
class Nurse:
    id: int
    name: str
    skill_level: int = 2            # 1=신규, 2=일반, 3=주임, 4=책임
    can_day: bool = True
    can_evening: bool = True
    can_night: bool = True          # False = 야간 금지
    fixed_shift: Optional[str] = None  # "D"/"E"/"N" = 매일 고정
    preceptor_of: Optional[int] = None # 프리셉팅 대상 간호사 ID
    weekday_only: bool = False         # True = 주말 근무 안함
    note: str = ""

    def to_dict(self):
        return {
            "id": self.id, "name": self.name, "skill_level": self.skill_level,
            "can_day": self.can_day, "can_evening": self.can_evening,
            "can_night": self.can_night, "fixed_shift": self.fixed_shift,
            "preceptor_of": self.preceptor_of, 
            "note": self.note,
        }

    @classmethod
    def from_dict(cls, d):
        d.setdefault("weekday_only", False)
        return cls(**d)


@dataclass
class Request:
    nurse_id: int
    day: int                        # 1~31
    code: str                       # "OFF","연차","D","E","N","D!","E!","N!"

    @property
    def is_hard(self) -> bool:
        return self.code in ("연차", "D!", "E!", "N!")

    @property
    def shift_type(self) -> Optional[str]:
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
    # 인원 배치
    weekday_min_day: int = 5
    weekday_min_evening: int = 5
    weekday_min_night: int = 2
    weekend_min_day: int = 4
    weekend_min_evening: int = 4
    weekend_min_night: int = 2

    # 금지 패턴
    ban_night_to_day: bool = True     # N→D
    ban_night_to_evening: bool = True # N→E
    ban_evening_to_day: bool = True   # E→D

    # 연속 제한
    max_consecutive_work: int = 5
    max_consecutive_night: int = 3
    night_off_after: int = 1          # 야간 연속 후 OFF 일수

    # 휴무
    min_monthly_off: int = 8
    max_monthly_off: int = 20
    max_consecutive_off: int = 5

    # 팀 구성
    night_senior_required: bool = True   # 야간 숙련자(3+) 필수
    ban_newbie_pair_night: bool = True    # 신규끼리 야간 금지

    def get_min_staff(self, shift: str, is_weekend: bool) -> int:
        if is_weekend:
            return {"D": self.weekend_min_day, "E": self.weekend_min_evening,
                    "N": self.weekend_min_night}[shift]
        else:
            return {"D": self.weekday_min_day, "E": self.weekday_min_evening,
                    "N": self.weekday_min_night}[shift]

    def to_dict(self):
        return {k: v for k, v in self.__dict__.items()}

    @classmethod
    def from_dict(cls, d):
        return cls(**d)


@dataclass
class Schedule:
    year: int
    month: int
    nurses: list  # list of Nurse
    rules: Rules
    requests: list  # list of Request
    # 결과: schedule_data[nurse_id][day] = "D"/"E"/"N"/"OFF"
    schedule_data: dict = field(default_factory=dict)

    @property
    def num_days(self) -> int:
        return calendar.monthrange(self.year, self.month)[1]

    def is_weekend(self, day: int) -> bool:
        wd = calendar.weekday(self.year, self.month, day)
        return wd >= 5  # 토=5, 일=6

    def weekday_name(self, day: int) -> str:
        names = ["월", "화", "수", "목", "금", "토", "일"]
        wd = calendar.weekday(self.year, self.month, day)
        return names[wd]

    def get_shift(self, nurse_id: int, day: int) -> str:
        return self.schedule_data.get(nurse_id, {}).get(day, "")

    def set_shift(self, nurse_id: int, day: int, shift: str):
        if nurse_id not in self.schedule_data:
            self.schedule_data[nurse_id] = {}
        self.schedule_data[nurse_id][day] = shift

    def get_day_count(self, nurse_id: int, shift: str) -> int:
        if nurse_id not in self.schedule_data:
            return 0
        return sum(1 for s in self.schedule_data[nurse_id].values() if s == shift)

    def get_staff_count(self, day: int, shift: str) -> int:
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
        if getattr(os.sys, 'frozen', False):
            base = os.path.dirname(os.sys.executable)
        else:
            base = os.path.dirname(os.path.abspath(__file__))
            base = os.path.dirname(base)  # engine/ 상위
        return os.path.join(base, "data")

    def _backup_dir(self):
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
            converted[str(nid)] = {str(d): s for d, s in days.items()}
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
