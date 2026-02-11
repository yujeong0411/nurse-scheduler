"""한국 공휴일 자동 감지 (holidays 패키지 사용)"""

from datetime import date, timedelta
import holidays


def get_holidays_for_period(start_date: date, num_days: int = 28) -> list[tuple[int, str]]:
    """시작일~시작일+num_days 기간의 공휴일 [(day_offset_1based, name), ...] 반환

    기간이 2개 월에 걸칠 수 있으므로 관련 연도/월 모두 조회
    """
    end_date = start_date + timedelta(days=num_days - 1)
    years = {start_date.year, end_date.year}
    kr = holidays.KR(years=years)

    result = []
    for offset in range(num_days):
        dt = start_date + timedelta(days=offset)
        if dt in kr:
            result.append((offset + 1, kr[dt]))  # 1-based day offset
    return result


def get_holidays_for_month(year: int, month: int) -> list[tuple[int, str]]:
    """해당 연월의 공휴일 [(day, name), ...] 반환 (하위 호환)"""
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
