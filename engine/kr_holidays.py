"""한국 공휴일 자동 감지 (holidays 패키지 사용)"""

from datetime import date, timedelta
import holidays


def _make_kr(years) -> holidays.HolidayBase:
    """한국 법정 공휴일, 한국어 이름으로 반환"""
    try:
        return holidays.country_holidays('KR', years=years, language='ko')
    except Exception:
        return holidays.KR(years=years)


def get_holidays_for_period(start_date: date, num_days: int = 28) -> list[tuple[date, str]]:
    """시작일~시작일+num_days 기간의 공휴일 [(date, name), ...] 반환

    기간이 2개 월에 걸칠 수 있으므로 관련 연도/월 모두 조회
    """
    end_date = start_date + timedelta(days=num_days - 1)
    years = {start_date.year, end_date.year}
    kr = _make_kr(years)

    result = []
    for offset in range(num_days):
        dt = start_date + timedelta(days=offset)
        if dt in kr:
            result.append((dt, kr[dt]))
    return result


def get_holidays_for_month(year: int, month: int) -> list[tuple[int, str]]:
    """해당 연월의 공휴일 [(day, name), ...] 반환 (하위 호환)"""
    kr = _make_kr(year)
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
