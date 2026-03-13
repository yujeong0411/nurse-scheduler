"""근무신청 저장·조회·현황·엑셀 export"""
import io
import os
import sys
import tempfile
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from ..database import get_db, db_nurses, get_period_by_id
from ..deps import get_current_admin, get_current_any
from ..schemas import RequestOut, RequestsUpsertBody, SubmissionStatus
from ..config import settings

router = APIRouter(prefix="/requests", tags=["근무신청"])


def _row_to_out(row: dict) -> RequestOut:
    return RequestOut(
        id=row["id"],
        nurse_id=row["nurse_id"],
        day=row["day"],
        code=row["code"],
        is_or=row.get("is_or", False),
        note=row.get("note") or '',
        submitted_at=str(row.get("submitted_at", "")),
    )


@router.get("/{period_id}", response_model=list[RequestOut])
def get_all_requests(period_id: str, _: dict = Depends(get_current_admin)):
    """전체 간호사 신청 조회 (관리자)"""
    db = get_db()
    res = db.table("requests").select("*").eq("period_id", period_id).execute()
    return [_row_to_out(r) for r in res.data]


@router.get("/{period_id}/me", response_model=list[RequestOut])
def get_my_requests(period_id: str, current: dict = Depends(get_current_any)):
    """본인 신청만 조회 (간호사)"""
    db = get_db()
    nurse_id = current["sub"]
    res = (
        db.table("requests")
        .select("*")
        .eq("period_id", period_id)
        .eq("nurse_id", nurse_id)
        .execute()
    )
    return [_row_to_out(r) for r in res.data]


@router.get("/{period_id}/status", response_model=list[SubmissionStatus])
def get_submission_status(period_id: str, _: dict = Depends(get_current_admin)):
    """각 간호사 제출 여부 + 제출 시각"""
    db = get_db()
    nurses = db_nurses(db).order("sort_order").execute().data

    # 제출한 간호사 목록 (최신 submitted_at 기준)
    req_res = (
        db.table("requests")
        .select("*")
        .eq("period_id", period_id)
        .order("submitted_at", desc=True)
        .execute()
    )
    submitted_map: dict[str, str] = {}
    for r in req_res.data:
        nid = r["nurse_id"]
        if nid not in submitted_map:
            submitted_map[nid] = str(r.get("submitted_at", ""))

    return [
        SubmissionStatus(
            nurse_id=n["id"],
            name=n["name"],
            submitted_at=submitted_map.get(n["id"]),
        )
        for n in nurses
    ]


@router.put("/{period_id}/{nurse_id}", response_model=list[RequestOut])
def upsert_requests(
    period_id: str,
    nurse_id: str,
    body: RequestsUpsertBody,
    current: dict = Depends(get_current_any),
):
    """간호사 본인 또는 관리자가 신청 일괄 저장"""
    # 권한 확인: nurse는 본인만
    if current["role"] == "nurse" and current["sub"] != nurse_id:
        raise HTTPException(403, "본인 신청만 수정할 수 있습니다.")

    db = get_db()
    # period 유효성
    period = get_period_by_id(db, period_id)
    if not period:
        raise HTTPException(404, "해당 기간을 찾을 수 없습니다.")

    # 마감 시간 체크 (간호사만)
    if current["role"] == "nurse" and period.get("deadline"):
        dl_str = period["deadline"]
        try:
            dl_dt = datetime.fromisoformat(dl_str if "T" in dl_str else dl_str + "T23:59")
            if datetime.now() > dl_dt:
                raise HTTPException(403, "신청 마감이 지났습니다.")
        except HTTPException:
            raise
        except Exception:
            pass

    now_iso = datetime.utcnow().isoformat()

    # 기존 신청 전체 삭제 후 재삽입
    db.table("requests").delete().eq("period_id", period_id).eq("nurse_id", nurse_id).execute()

    if not body.items:
        return []

    rows = [
        {
            "period_id": period_id,
            "nurse_id": nurse_id,
            "day": item.day,
            "code": item.code,
            "is_or": item.is_or,
            "note": item.note or '',
            "submitted_at": now_iso,
        }
        for item in body.items
    ]
    res = db.table("requests").insert(rows).execute()
    return [_row_to_out(r) for r in res.data]


@router.get("/{period_id}/export")
def export_requests_excel(period_id: str, _: dict = Depends(get_current_admin)):
    """신청현황 xlsx 다운로드 — request_example 포맷"""
    db = get_db()
    period = get_period_by_id(db, period_id)
    if not period:
        raise HTTPException(404)

    nurses = db_nurses(db).order("sort_order").execute().data
    req_res = db.table("requests").select("*").eq("period_id", period_id).execute().data

    # 부서명 조회
    try:
        dept_res = db.table("departments").select("name").eq("id", settings.department_id).single().execute()
        dept_name = dept_res.data.get("name", "") if dept_res.data else ""
    except Exception:
        dept_name = ""

    # nurse_id → {day: {codes: [...], note: str}} 맵
    req_map: dict[str, dict[int, dict]] = {n["id"]: {} for n in nurses}
    for r in req_res:
        nid = r["nurse_id"]
        day = r["day"]
        code = r["code"]
        is_or = r.get("is_or", False)
        note = r.get("note") or ""
        if day not in req_map.setdefault(nid, {}):
            req_map[nid][day] = {"codes": [], "note": note}
        req_map[nid][day]["codes"].append((code, is_or))
        if note:
            req_map[nid][day]["note"] = note

    from openpyxl import Workbook
    from openpyxl.styles import PatternFill, Font, Alignment, Border, Side
    from openpyxl.utils import get_column_letter
    from datetime import date, timedelta

    start = date.fromisoformat(period["start_date"])
    end = start + timedelta(days=27)
    WD = ["월", "화", "수", "목", "금", "토", "일"]
    NUM_DAYS = 28

    wb = Workbook()
    ws = wb.active
    ws.title = "근무신청현황"

    YELLOW_FILL = PatternFill("solid", fgColor="fcfb92")
    WEEKEND_FILL = PatternFill("solid", fgColor="F2F2F2")
    HEADER_FILL = PatternFill("solid", fgColor="D9D9D9")
    TITLE_FILL = PatternFill("solid", fgColor="4472C4")
    CENTER = Alignment(horizontal="center", vertical="center")
    BLACK_BORDER = Border(
        left=Side(style="thin", color="000000"),
        right=Side(style="thin", color="000000"),
        top=Side(style="thin", color="000000"),
        bottom=Side(style="thin", color="000000"),
    )

    def apply_border(cell):
        cell.border = BLACK_BORDER

    # ── 행1: 타이틀 (병합)
    total_cols = NUM_DAYS + 1  # 이름 열 + 날짜 열
    title_text = f"{start.strftime('%Y.%m.%d')} ~ {end.strftime('%Y.%m.%d')}  {dept_name} 근무신청표"
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=total_cols)
    title_cell = ws.cell(1, 1, title_text)
    title_cell.font = Font(bold=True, size=12, color="FFFFFF")
    title_cell.fill = TITLE_FILL
    title_cell.alignment = CENTER
    ws.row_dimensions[1].height = 22

    # ── 행2: 날짜
    c0 = ws.cell(2, 1, "")
    c0.fill = HEADER_FILL; apply_border(c0)
    for i in range(NUM_DAYS):
        d = start + timedelta(days=i)
        wd = d.weekday()
        cell = ws.cell(2, i + 2, f"{d.day}일")
        cell.alignment = CENTER
        cell.font = Font(bold=True, size=9, color="CC0000" if wd >= 5 else "000000")
        cell.fill = WEEKEND_FILL if wd >= 5 else HEADER_FILL
        apply_border(cell)

    # ── 행3: 이름 헤더 + 요일
    c1 = ws.cell(3, 1, "이름")
    c1.font = Font(bold=True); c1.alignment = CENTER; c1.fill = HEADER_FILL; apply_border(c1)
    for i in range(NUM_DAYS):
        d = start + timedelta(days=i)
        wd = d.weekday()
        cell = ws.cell(3, i + 2, WD[wd])
        cell.alignment = CENTER
        cell.font = Font(size=9, color="CC0000" if wd >= 5 else "333333")
        cell.fill = WEEKEND_FILL if wd >= 5 else HEADER_FILL
        apply_border(cell)

    # ── 행4+: 간호사별
    for nurse in nurses:
        row_idx = ws.max_row + 1
        shifts_raw = req_map.get(nurse["id"], {})

        nc = ws.cell(row_idx, 1, nurse["name"])
        nc.alignment = CENTER; apply_border(nc)

        for i in range(NUM_DAYS):
            day = i + 1
            d = start + timedelta(days=i)
            wd = d.weekday()
            col = i + 2
            cell = ws.cell(row_idx, col)

            fixed_off = nurse.get("fixed_weekly_off")
            is_fixed_off = fixed_off is not None and fixed_off != "" and int(fixed_off) == wd

            if is_fixed_off:
                cell.value = "주"
                cell.fill = PatternFill("solid", fgColor="FFFFFF")
                cell.alignment = CENTER
                cell.font = Font(size=9, color="666666")
            elif shifts_raw.get(day):
                entry = shifts_raw[day]
                codes = entry["codes"]
                note = entry.get("note", "")
                or_entries = [c for c, is_or in codes if is_or]
                non_or = [c for c, is_or in codes if not is_or]
                if or_entries:
                    cell.value = "/".join(or_entries)
                else:
                    cell.value = non_or[0] if non_or else ""
                cell.fill = YELLOW_FILL
                cell.alignment = CENTER
                if note:
                    from openpyxl.comments import Comment
                    cell.comment = Comment(note, "간호사")
            else:
                cell.value = ""
                if wd >= 5:
                    cell.fill = WEEKEND_FILL
                cell.alignment = CENTER
            apply_border(cell)

    # ── 열 너비
    ws.column_dimensions["A"].width = 12
    for i in range(NUM_DAYS):
        ws.column_dimensions[get_column_letter(i + 2)].width = 6

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)

    from urllib.parse import quote
    filename = f"{start.strftime('%Y.%m.%d')}~{end.strftime('%Y.%m.%d')}_신청표.xlsx"
    encoded = quote(filename, safe='')
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{encoded}"},
    )
