"""한국 공휴일 자동 감지 (holidays 패키지 사용)"""

import holidays


def get_holidays_for_month(year: int, month: int) -> list[tuple[int, str]]:
    """해당 연월의 공휴일 [(day, name), ...] 반환"""
    kr = holidays.KR(years=year)
    return sorted(
        (dt.day, name)
        for dt, name in kr.items()
        if dt.month == month
    )


def get_holiday_days(year: int, month: int) -> list[int]:
    """해당 월 공휴일 날짜(day)만 반환"""
    return [day for day, _ in get_holidays_for_month(year, month)]


def get_holidays_with_names(year: int, month: int) -> dict[int, str]:
    """해당 월 {day: name} 딕셔너리"""
    return dict(get_holidays_for_month(year, month))
