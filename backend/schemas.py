"""전체 Pydantic 요청/응답 모델"""
from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Optional, Any
from datetime import date


# ── 인증 ──────────────────────────────────────────────────────────────

class AdminLoginRequest(BaseModel):
    password: str

class NurseLoginRequest(BaseModel):
    nurse_id: str
    pin: str

class TokenResponse(BaseModel):
    token: str
    role: str
    name: str | None = None

class PinChangeRequest(BaseModel):
    old_pin: str
    new_pin: str = Field(..., min_length=4, max_length=6, pattern=r"^\d+$")

class AdminPwChangeRequest(BaseModel):
    old_pw: str
    new_pw: str = Field(..., min_length=4)

class AdminPinResetRequest(BaseModel):
    nurse_id: str


# ── 간호사 ─────────────────────────────────────────────────────────────

class NurseBase(BaseModel):
    name: str
    role: str = ""
    grade: str = ""
    is_pregnant: bool = False
    is_male: bool = False
    is_4day_week: bool = False
    fixed_weekly_off: Optional[int] = None
    vacation_days: int = 0
    prev_month_n: int = 0
    pending_sleep: bool = False
    menstrual_used: bool = False
    prev_tail_shifts: list[str] = []
    note: str = ""
    sort_order: int = 0

class NurseCreate(NurseBase):
    pass

class NurseUpdate(NurseBase):
    pass

class NurseOut(NurseBase):
    id: str

    model_config = {"from_attributes": True}


# ── 규칙 ──────────────────────────────────────────────────────────────

class RulesOut(BaseModel):
    daily_d: int = 7
    daily_e: int = 8
    daily_n: int = 7
    daily_m: int = 1
    max_n_per_month: int = 6
    max_consecutive_n: int = 3
    off_after_2n: int = 2
    max_consecutive_work: int = 5
    min_weekly_off: int = 2
    ban_reverse_order: bool = True
    min_chief_per_shift: int = 1
    min_senior_per_shift: int = 2
    pregnant_poff_interval: int = 4
    menstrual_leave: bool = True
    sleep_n_monthly: int = 7
    sleep_n_bimonthly: int = 11
    public_holidays: list[int] = []

class RulesUpdate(RulesOut):
    pass


# ── 설정 (기간/마감) ────────────────────────────────────────────────────

class SettingsOut(BaseModel):
    period_id: str | None = None
    start_date: str | None = None   # "YYYY-MM-DD"
    deadline: str | None = None

class SettingsUpdate(BaseModel):
    start_date: str                 # "YYYY-MM-DD"
    deadline: str | None = None


# ── 근무신청 ───────────────────────────────────────────────────────────

class RequestItem(BaseModel):
    day: int = Field(..., ge=1, le=28)
    code: str
    is_or: bool = False

class RequestOut(RequestItem):
    id: str
    nurse_id: str
    submitted_at: str | None = None

class SubmissionStatus(BaseModel):
    nurse_id: str
    name: str
    submitted_at: str | None = None   # None이면 미제출

class RequestsUpsertBody(BaseModel):
    items: list[RequestItem]


# ── 근무표 ─────────────────────────────────────────────────────────────

class GenerateRequest(BaseModel):
    period_id: str
    timeout_seconds: int = 180

class JobStatusOut(BaseModel):
    job_id: str
    status: str                     # pending|running|done|failed
    schedule_id: str | None = None
    error_msg: str | None = None

class CellUpdate(BaseModel):
    nurse_id: str
    day: int = Field(..., ge=1, le=28)
    new_shift: str
    force: bool = False             # 위반 있어도 강제 저장

class CellUpdateResult(BaseModel):
    violations: list[str]
    saved: bool

class ScheduleOut(BaseModel):
    id: str
    period_id: str
    schedule_data: dict[str, dict[str, str]]   # {nurse_id: {day_str: shift}}
    nurses: list[NurseOut]
    score: int | None = None
    grade: str | None = None
    eval_details: dict[str, Any] = {}

class EvaluateOut(BaseModel):
    score: float
    grade: str
    violation_details: list[str]
    request_fulfilled: dict[str, Any]
    bad_patterns: dict[str, int]
    deductions: list[Any]
