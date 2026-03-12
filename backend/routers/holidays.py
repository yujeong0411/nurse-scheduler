"""한국 공휴일 조회 (인증 불필요)"""
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/holidays", tags=["공휴일"])


class HolidayItem(BaseModel):
    day: int
    name: str


@router.get("", response_model=list[HolidayItem])
def get_holidays(year: int, month: int):
    import sys, os
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    if root not in sys.path:
        sys.path.insert(0, root)

    from engine.kr_holidays import get_holidays_for_month
    result = get_holidays_for_month(year, month)
    return [HolidayItem(day=day, name=name) for day, name in result]
