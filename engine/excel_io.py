"""엑셀 가져오기 / 내보내기 — 응급실 간호사 근무표

가져오기:
  - 근무신청표 (달력 격자): 간호사 이름 + 요청사항
  - 근무표 규칙: 간호사 속성 (역할, 직급, 특수조건)

내보내기:
  - 근무표 시트 (17종 근무/휴무 컬러)
  - 통계 시트
"""
import calendar
import re
from datetime import date, timedelta
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from engine.models import (
    Nurse, Request, Rules, Schedule,
    WORK_SHIFTS, OFF_TYPES, ALL_CODES,
)


# ══════════════════════════════════════════
# 스타일 정의
# ══════════════════════════════════════════

# 근무별 색상
FILLS = {
    # "D":   PatternFill(start_color="DAF0F3", fill_type="solid"),
    # "D9":  PatternFill(start_color="B4E1E8", fill_type="solid"),  # 중간 계열
    # "D1":  PatternFill(start_color="B4E1E8", fill_type="solid"),  # 중간 계열
    # "중1":  PatternFill(start_color="FDEBD0", fill_type="solid"), # 중간 계열
    # "중2":  PatternFill(start_color="FDEBD0", fill_type="solid"), # 중간 계열
    # "E":   PatternFill(start_color="FDE9D9", fill_type="solid"),
    # "N":   PatternFill(start_color="E4DFEC", fill_type="solid"),
    "OFF": PatternFill(start_color="fcfb92", fill_type="solid"),
    "주":   PatternFill(start_color="fcfb92", fill_type="solid"),
    "법휴": PatternFill(start_color="fcfb92", fill_type="solid"),
    "생휴":   PatternFill(start_color="fcfb92", fill_type="solid"),
    "수면": PatternFill(start_color="fcfb92", fill_type="solid"),
    "POFF": PatternFill(start_color="fcfb92", fill_type="solid"),
    "휴가":   PatternFill(start_color="fcfb92", fill_type="solid"),
    "특휴": PatternFill(start_color="fcfb92", fill_type="solid"),
    "공가":   PatternFill(start_color="fcfb92", fill_type="solid"),
    "경가":   PatternFill(start_color="fcfb92", fill_type="solid"),
}
FONTS = {
    "D":   Font(color="0775fa", bold=True, size=9),
    # "D9":  Font(color="2E75B6", bold=True, size=9),  # 중간 계열
    # "D1":  Font(color="2E75B6", bold=True, size=9),  # 중간 계열
    # "중1":  Font(color="BF8F00", bold=True, size=9),  # 중간 계열
    # "중2":  Font(color="BF8F00", bold=True, size=9),  # 중간 계열
    "E":   Font(color="d17804", bold=True, size=9),
    "N":   Font(color="d61506", bold=True, size=9),
    # "OFF": Font(color="548235", bold=True, size=9),
    # "주":   Font(color="006100", bold=True, size=9),
    # "법휴": Font(color="9C5700", bold=True, size=9),
    # "생휴":   Font(color="CC0000", bold=True, size=9),
    # "수면": Font(color="674EA7", bold=True, size=9),
    # "POFF": Font(color="BF6000", bold=True, size=9),
}

HEADER_FILL = PatternFill(start_color="013976", fill_type="solid")
HEADER_FONT = Font(color="FFFFFF", bold=True, size=10)
WEEKEND_FILL = PatternFill(start_color="F2F2F2", fill_type="solid")
SHORTAGE_FILL = PatternFill(start_color="FFCCCC", fill_type="solid")
THIN_BORDER = Border(
    left=Side(style="thin", color="D0D0D0"),
    right=Side(style="thin", color="D0D0D0"),
    top=Side(style="thin", color="D0D0D0"),
    bottom=Side(style="thin", color="D0D0D0"),
)
CENTER = Alignment(horizontal="center", vertical="center")



# ══════════════════════════════════════════
# 내보내기
# ══════════════════════════════════════════

def export_schedule(schedule: Schedule, rules: Rules, filepath: str):
    """근무표 + 통계를 엑셀로 내보내기"""
    wb = Workbook()

    # ── Sheet 1: 근무표 ──
    ws = wb.active
    ws.title = "근무표"

    start_date = schedule.start_date
    end_date = schedule.date_of(28)
    num_days = schedule.num_days
    nurses = schedule.nurses
    weekday_names = ["월", "화", "수", "목", "금", "토", "일"]

    # 타이틀
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=num_days + 8)
    title = f"{start_date.strftime('%Y.%m.%d')} ~ {end_date.strftime('%Y.%m.%d')} 응급실 근무표"
    ws.cell(1, 1, title)
    ws.cell(1, 1).font = Font(bold=True, size=14, color="013976")
    ws.cell(1, 1).alignment = Alignment(horizontal="center")

    # 헤더 (행3)
    stat_cols = ["D", "E", "N", "OFF", "총근무", "주말"]
    # 중간근무 추가 시: ["D", "M", "E", "N", "OFF", "총근무", "주말"]
    headers = ["이름"] + [f"{d}" for d in range(1, num_days + 1)] + stat_cols
    for c, h in enumerate(headers, 1):
        cell = ws.cell(3, c, h)
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.alignment = CENTER
        cell.border = THIN_BORDER

    # 요일 행 (행4)
    ws.cell(4, 1, "요일")
    ws.cell(4, 1).font = Font(bold=True, size=9)
    ws.cell(4, 1).alignment = CENTER
    for d in range(1, num_days + 1):
        wd = schedule.weekday_index(d)
        cell = ws.cell(4, d + 1, weekday_names[wd])
        cell.alignment = CENTER
        cell.font = Font(size=8, bold=True, color="CC0000" if wd >= 5 else "333333")
        if wd >= 5:
            cell.fill = WEEKEND_FILL

    # 간호사별 데이터
    weekend_days = [d for d in range(1, num_days + 1) if schedule.is_weekend(d)]

    for i, nurse in enumerate(nurses):
        row = 5 + i
        ws.cell(row, 1, nurse.name)
        ws.cell(row, 1).font = Font(bold=True, size=10)
        ws.cell(row, 1).alignment = CENTER
        ws.cell(row, 1).border = THIN_BORDER

        d_cnt, e_cnt, n_cnt, off_cnt = 0, 0, 0, 0
        # m_cnt = 0  # 중간근무 추가 시

        for d in range(1, num_days + 1):
            shift = schedule.get_shift(nurse.id, d)
            cell = ws.cell(row, d + 1, shift)
            cell.alignment = CENTER
            cell.border = THIN_BORDER

            if shift in FILLS:
                cell.fill = FILLS[shift]
            elif schedule.weekday_index(d) >= 5:
                cell.fill = WEEKEND_FILL
            if shift in FONTS:
                cell.font = FONTS[shift]

            if shift == "D":
                d_cnt += 1
            elif shift == "E":
                e_cnt += 1
            elif shift == "N":
                n_cnt += 1
            # elif shift in ("D9", "D1", "중1", "중2"):  # 중간근무 추가 시
            #     m_cnt += 1
            elif shift in OFF_TYPES or shift == "OFF":
                off_cnt += 1

        total_work = d_cnt + e_cnt + n_cnt  # + m_cnt
        wk_work = sum(
            1 for d in weekend_days
            if schedule.get_shift(nurse.id, d) in WORK_SHIFTS
        )

        stat_vals = [d_cnt, e_cnt, n_cnt, off_cnt, total_work, wk_work]
        # 중간근무 추가 시: [d_cnt, m_cnt, e_cnt, n_cnt, off_cnt, total_work, wk_work]
        for j, val in enumerate(stat_vals):
            cell = ws.cell(row, num_days + 2 + j, val)
            cell.alignment = CENTER
            cell.border = THIN_BORDER
            cell.font = Font(bold=True, size=9)

    # 집계 행
    # 중간근무 추가 시: ["D", "M", "E", "N"]
    sep_row = 5 + len(nurses)
    for si, shift_type in enumerate(["D", "E", "N"]):
        agg_row = sep_row + 1 + si
        ws.cell(agg_row, 1, f"{shift_type} 인원")
        ws.cell(agg_row, 1).font = Font(bold=True, size=9)
        ws.cell(agg_row, 1).alignment = CENTER

        for d in range(1, num_days + 1):
            count = sum(
                1 for n in nurses
                if schedule.get_shift(n.id, d) == shift_type
            )
            cell = ws.cell(agg_row, d + 1, count)
            cell.alignment = CENTER
            cell.border = THIN_BORDER
            cell.font = Font(bold=True, size=9)

            min_req = rules.get_daily_staff(shift_type)
            if count < min_req:
                cell.fill = SHORTAGE_FILL
                cell.font = Font(bold=True, size=9, color="CC0000")

    # 컬럼 너비
    ws.column_dimensions["A"].width = 12
    for d in range(1, num_days + 1):
        ws.column_dimensions[get_column_letter(d + 1)].width = 5
    for j in range(len(stat_cols)):
        ws.column_dimensions[get_column_letter(num_days + 2 + j)].width = 7

    # ── Sheet 2: 통계 ──
    ws2 = wb.create_sheet("통계")
    ws2.cell(1, 1, f"{start_date.strftime('%Y.%m.%d')} ~ {end_date.strftime('%Y.%m.%d')} 개인별 통계")
    ws2.cell(1, 1).font = Font(bold=True, size=14, color="013976")

    stat_headers = ["이름", "직급", "역할", "D", "E", "N",
                    "OFF", "총근무", "N비율", "주말근무"]
    # 중간근무 추가 시: "D", "M", "E", "N", ...
    for c, h in enumerate(stat_headers, 1):
        cell = ws2.cell(3, c, h)
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.alignment = CENTER

    for i, nurse in enumerate(nurses):
        row = 4 + i
        d_cnt = sum(
            1 for d in range(1, num_days + 1)
            if schedule.get_shift(nurse.id, d) == "D"
        )
        # m_cnt = sum(... in ("D9","D1","중1","중2"))  # 중간근무 추가 시
        e_cnt = sum(
            1 for d in range(1, num_days + 1)
            if schedule.get_shift(nurse.id, d) == "E"
        )
        n_cnt = schedule.get_day_count(nurse.id, "N")
        off_cnt = num_days - d_cnt - e_cnt - n_cnt  # - m_cnt
        total_work = d_cnt + e_cnt + n_cnt  # + m_cnt
        n_ratio = f"{n_cnt / total_work * 100:.0f}%" if total_work > 0 else "0%"
        wk_work = sum(
            1 for d in weekend_days
            if schedule.get_shift(nurse.id, d) in WORK_SHIFTS
        )

        data = [nurse.name, nurse.grade or "일반", nurse.role or "-",
                d_cnt, e_cnt, n_cnt, off_cnt, total_work, n_ratio, wk_work]
        for c, val in enumerate(data, 1):
            cell = ws2.cell(row, c, val)
            cell.alignment = CENTER
            cell.border = THIN_BORDER

    for c in range(1, len(stat_headers) + 1):
        ws2.column_dimensions[get_column_letter(c)].width = 10

    wb.save(filepath)


# ══════════════════════════════════════════
# 가져오기: 근무 규칙 엑셀 → 간호사 속성
# ══════════════════════════════════════════

def import_nurse_rules(filepath: str) -> list[Nurse]:
    """근무표_규칙.xlsx에서 간호사 목록 + 속성 불러오기

    형식:
      C열: 이름
      D열: 비고1 (역할) — 책임만, 외상, 혼자 관찰, 급성구역, 준급성, 격리구역(소아)
      E열: 비고2 (직급) — 책임, 서브차지
      F열: 비고3 (특수) — 임산부, 남자
      G열: 비고4 (근무형태) — 주4일제
    """
    wb = load_workbook(filepath, read_only=True, data_only=True)
    ws = wb.active

    # 헤더 행 찾기 ("이름" 포함 행)
    header_row = None
    name_col = None
    for row in ws.iter_rows(min_row=1, max_row=10):
        for cell in row:
            val = str(cell.value).strip() if cell.value else ""
            if val == "이름":
                header_row = cell.row
                name_col = cell.column
                break
        if header_row:
            break

    if not header_row or not name_col:
        wb.close()
        return []

    # 비고 컬럼 위치 (이름 기준 상대)
    # 일반적으로 D=비고1, E=비고2, F=비고3, G=비고4
    col_role = name_col + 1    # 비고1
    col_grade = name_col + 2   # 비고2
    col_special = name_col + 3 # 비고3
    col_work = name_col + 4    # 비고4

    nurses = []
    nurse_id = 1

    for row in ws.iter_rows(min_row=header_row + 1):
        # 이름
        name_cell = row[name_col - 1] if name_col - 1 < len(row) else None
        name = str(name_cell.value).strip() if name_cell and name_cell.value else ""
        if not name:
            continue

        nurse = Nurse(id=nurse_id, name=name)

        # 비고1: 역할
        if col_role - 1 < len(row):
            val = str(row[col_role - 1].value).strip() if row[col_role - 1].value else ""
            if val:
                nurse.role = val

        # 비고2: 직급
        if col_grade - 1 < len(row):
            val = str(row[col_grade - 1].value).strip() if row[col_grade - 1].value else ""
            if val in ("책임", "서브차치", "서브차지"):
                nurse.grade = "서브차지" if "서브" in val else val

        # 비고3: 특수
        if col_special - 1 < len(row):
            val = str(row[col_special - 1].value).strip() if row[col_special - 1].value else ""
            if "임산부" in val:
                nurse.is_pregnant = True
            if "남자" in val or "남" == val:
                nurse.is_male = True

        # 비고4: 근무형태
        if col_work - 1 < len(row):
            val = str(row[col_work - 1].value).strip() if row[col_work - 1].value else ""
            if "주4" in val or "4일" in val:
                nurse.is_4day_week = True

        nurses.append(nurse)
        nurse_id += 1

    wb.close()
    return nurses


# ══════════════════════════════════════════
# 가져오기: 근무신청표 → 요청사항
# ══════════════════════════════════════════

def _normalize_code(val: str) -> str | None:
    """엑셀 셀 값을 표준 코드로 변환

    Returns: 표준 코드 또는 None (무시할 값)
    """
    val = val.strip()
    if not val:
        return None

    # 대소문자 통일
    upper = val.upper()

    # 제외 요청
    for s in ["D", "E", "N"]:
        no_space = val.replace(" ", "")
        if no_space == f"{s}제외":
            return f"{s} 제외"

    # 정확한 매칭
    exact_map = {
        "D": "D", "E": "E", "N": "N",
        "D9": "D", "D1": "D",
        "중1": "E", "중2": "E",
        "OFF": "OFF", "오프": "OFF",
        "주": "주", "주휴": "주",
        "법": "법휴", "법휴": "법휴",
        "생휴": "생휴", "생": "생휴",
        "수면": "수면",
        "VAC": "휴가", "휴가": "휴가", "휴": "휴가",
        "공가": "공가", "공": "공가",
        "경가": "경가", "경": "경가",
        "특휴": "특휴",
        "보수": "보수",
        "POFF": "POFF",
    }

    if upper in exact_map:
        return exact_map[upper]
    if val in exact_map:
        return exact_map[val]

    # "수면(1,2월)", "수면(2월)" 등 → "수면"
    if val.startswith("수면"):
        return "수면"

    # off 소문자
    if upper == "OFF":
        return "OFF"

    return None


def import_requests(
    filepath: str,
    nurses: list[Nurse],
    start_date: date,
) -> tuple[list[Request], dict[int, int]]:
    """근무신청표 엑셀에서 요청사항 + 간호사 속성 읽기

    Args:
        filepath: 엑셀 파일 경로
        nurses: 간호사 목록 (이름 매칭용, 속성도 업데이트됨)
        start_date: 스케줄 시작일

    Returns:
        (requests, weekly_off_map)
        - requests: Request 목록
        - weekly_off_map: {nurse_id: weekday_index} 고정 주휴 요일

    Side effects:
        nurses 리스트의 각 Nurse 객체에 아래 속성을 업데이트:
        - vacation_days: B열 (휴가 잔여일)
        - menstrual_used: C열 (생휴 이미 사용 여부)
        - pending_sleep: D열 (전월 수면 이월)

    형식 (응급실 실제):
      A열: 이름
      B열: 휴가 (잔여 연차)
      C열: 생휴 (1=이미 사용)
      D열: 수면 (값 있으면 전월 이월)
      E~AF열: 1일~28일 (코드 입력)
    """
    wb = load_workbook(filepath, read_only=True, data_only=True)
    ws = wb.active

    nurse_name_map = {n.name.strip(): n for n in nurses}
    num_days = 28

    # ── 헤더/날짜 열 찾기 ──
    header_row = None
    day_cols = {}  # {day: col_index}

    for row in ws.iter_rows(min_row=1, max_row=10):
        for cell in row:
            val = str(cell.value).strip() if cell.value else ""
            match = re.match(r"^(\d{1,2})일$", val)
            if match:
                d = int(match.group(1))
                if 1 <= d <= 31:
                    if header_row is None:
                        header_row = cell.row
                    if cell.row == header_row:
                        day_cols[d] = cell.column

    if not header_row or not day_cols:
        wb.close()
        return [], {}

    # ── 이름/휴가/생휴/수면 열 찾기 ──
    # 날짜 열 이전 컬럼에서만 검색 (뒤쪽 통계 영역 제외)
    min_day_col = min(day_cols.values())  # 첫 날짜 열 (보통 E=5)
    name_col = 1  # 기본 A열
    vac_col = None
    menst_col = None
    sleep_col = None

    for search_row in range(max(1, header_row - 1), header_row + 3):
        for row in ws.iter_rows(min_row=search_row, max_row=search_row,
                                max_col=min_day_col - 1):
            for cell in row:
                val = str(cell.value).strip() if cell.value else ""
                if val == "이름":
                    name_col = cell.column
                elif val in ("휴가", "연차"):
                    vac_col = cell.column
                elif val in ("생휴", "생리"):
                    menst_col = cell.column
                elif val == "수면":
                    sleep_col = cell.column

    # ── 데이터 시작 행 찾기 ──
    # header_row(날짜) 이후에 "이름"/"일"/"월" 등이 있으면 그 다음 행부터
    data_start = header_row + 1
    for check in ws.iter_rows(min_row=header_row + 1,
                              max_row=min(header_row + 3, ws.max_row),
                              max_col=min_day_col + 6):
        for cell in check:
            val = str(cell.value).strip() if cell.value else ""
            if val in ("이름", "일", "월", "화", "수", "목", "금", "토"):
                data_start = check[0].row + 1
                break
        else:
            continue
        break

    # ── 데이터 읽기 ──
    requests = []
    weekly_off_map = {}
    stop_words = {"off", "주", "수면", "생휴", "vac", "공가", "총"}

    nid_counter = max([n.id for n in nurses], default=0) + 1 # 새로운 ID 시작점
    
    for row in ws.iter_rows(min_row=data_start):
        # 이름
        name_cell = row[name_col - 1] if name_col - 1 < len(row) else None
        name = str(name_cell.value).strip() if name_cell and name_cell.value else ""
        if not name or name.lower() in stop_words:
            continue
        if name not in nurse_name_map:
            new_nurse = Nurse(id=nid_counter, name=name)
            nurses.append(new_nurse)        # 원본 리스트에 추가
            nurse_name_map[name] = new_nurse # 맵에 추가
            nid_counter += 1

        nurse = nurse_name_map[name]
        nid = nurse.id

        # ── B열: 휴가 잔여일 ──
        if vac_col and vac_col - 1 < len(row):
            v = row[vac_col - 1].value
            if v is not None:
                try:
                    nurse.vacation_days = int(v)
                except (ValueError, TypeError):
                    pass

        # ── C열: 생휴 사용 여부 ──
        if menst_col and menst_col - 1 < len(row):
            v = row[menst_col - 1].value
            if v is not None:
                try:
                    nurse.menstrual_used = int(v) >= 1
                except (ValueError, TypeError):
                    nurse.menstrual_used = bool(v)

        # ── D열: 수면 이월 ──
        if sleep_col and sleep_col - 1 < len(row):
            v = row[sleep_col - 1].value
            if v is not None:
                val_str = str(v).strip()
                # "1", "1,2월 수면", 숫자 → 이월 있음
                nurse.pending_sleep = bool(val_str)

        # ── 날짜별 요청 ──
        first_weekly = None

        for d, col in day_cols.items():
            if d > num_days:
                continue
            cell = row[col - 1] if col - 1 < len(row) else None
            val = str(cell.value).strip() if cell and cell.value else ""
            code = _normalize_code(val)

            if code is None:
                continue

            # "주" → 고정 주휴 요일 감지
            if code == "주":
                wd = (start_date + timedelta(days=d - 1)).weekday()
                if first_weekly is None:
                    first_weekly = wd

            requests.append(Request(nurse_id=nid, day=d, code=code))

        if first_weekly is not None:
            weekly_off_map[nid] = first_weekly

    wb.close()
    return requests, weekly_off_map


def import_nurses_from_request(filepath: str) -> list[str]:
    """근무신청표에서 간호사 이름 목록만 추출

    Returns: 이름 리스트 (순서 유지)
    """
    wb = load_workbook(filepath, read_only=True, data_only=True)
    ws = wb.active

    # ── 날짜 헤더 행 + 첫 날짜 열 찾기 ──
    header_row = None
    min_day_col = None
    for row in ws.iter_rows(min_row=1, max_row=10):
        for cell in row:
            val = str(cell.value).strip() if cell.value else ""
            if re.match(r"^\d{1,2}일$", val):
                if header_row is None:
                    header_row = cell.row
                if cell.row == header_row:
                    if min_day_col is None or cell.column < min_day_col:
                        min_day_col = cell.column
        if header_row:
            break

    if not header_row:
        wb.close()
        return []

    # ── 이름 열 찾기 (import_requests와 동일 로직) ──
    name_col = 1  # 기본 A열
    for search_row in range(max(1, header_row - 1), header_row + 3):
        for row in ws.iter_rows(min_row=search_row, max_row=search_row,
                                max_col=(min_day_col or 5) - 1):
            for cell in row:
                val = str(cell.value).strip() if cell.value else ""
                if val == "이름":
                    name_col = cell.column

    # ── 데이터 시작 행 찾기 (import_requests와 동일 로직) ──
    data_start = header_row + 1
    for check in ws.iter_rows(min_row=header_row + 1,
                              max_row=min(header_row + 3, ws.max_row),
                              max_col=(min_day_col or 5) + 6):
        for cell in check:
            val = str(cell.value).strip() if cell.value else ""
            if val in ("이름", "일", "월", "화", "수", "목", "금", "토"):
                data_start = check[0].row + 1
                break
        else:
            continue
        break

    # ── 이름 추출 ──
    names = []
    stop_words = {"off", "주", "수면", "생휴", "vac", "공가", "총"}

    for row in ws.iter_rows(min_row=data_start):
        cell = row[name_col - 1] if name_col - 1 < len(row) else None
        val = str(cell.value).strip() if cell and cell.value else ""
        if not val:
            continue
        if val.lower() in stop_words:
            break  # 집계 행 도달
        names.append(val)

    wb.close()
    return names
