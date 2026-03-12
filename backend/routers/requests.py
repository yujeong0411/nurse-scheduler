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

    # 마감일 체크 (간호사만)
    if current["role"] == "nurse" and period.get("deadline"):
        from datetime import date
        today = date.today()
        deadline = date.fromisoformat(period["deadline"])
        if today > deadline:
            raise HTTPException(403, "신청 마감이 지났습니다.")

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
            "submitted_at": now_iso,
        }
        for item in body.items
    ]
    res = db.table("requests").insert(rows).execute()
    return [_row_to_out(r) for r in res.data]


@router.get("/{period_id}/export")
def export_requests_excel(period_id: str, _: dict = Depends(get_current_admin)):
    """신청현황 xlsx 다운로드 — prototype handleExport 로직 서버 이전"""
    db = get_db()
    period = get_period_by_id(db, period_id)
    if not period:
        raise HTTPException(404)

    nurses = db_nurses(db).order("sort_order").execute().data
    req_res = db.table("requests").select("*").eq("period_id", period_id).execute().data

    # nurse_id → {day: code} 맵 구성
    req_map: dict[str, dict[int, str]] = {n["id"]: {} for n in nurses}
    submitted_at_map: dict[str, str] = {}
    for r in req_res:
        nid = r["nurse_id"]
        req_map.setdefault(nid, {})[r["day"]] = r["code"]
        submitted_at_map.setdefault(nid, str(r.get("submitted_at", "")))

    from openpyxl import Workbook
    from openpyxl.styles import PatternFill, Font, Alignment
    from datetime import date, timedelta

    start = date.fromisoformat(period["start_date"])
    WD = ["월", "화", "수", "목", "금", "토", "일"]

    wb = Workbook()
    ws = wb.active
    ws.title = "근무신청현황"

    # 헤더
    header = ["이름", "역할", "직급"]
    for i in range(28):
        d = start + timedelta(days=i)
        wd = WD[d.weekday()]
        header.append(f"{d.month}/{d.day}({wd})")
    header.append("제출일시")
    ws.append(header)

    blue_fill  = PatternFill("solid", fgColor="1D4ED8")
    yellow_fill = PatternFill("solid", fgColor="FFFF00")
    gray_fill   = PatternFill("solid", fgColor="C0C0C0")
    white_font  = Font(color="FFFFFF", bold=True)
    bold_font   = Font(bold=True)

    for cell in ws[1]:
        cell.fill = blue_fill
        cell.font = white_font
        cell.alignment = Alignment(horizontal="center")

    for nurse in nurses:
        row_data = [nurse["name"], nurse.get("role", ""), nurse.get("grade", "")]
        shifts = req_map.get(nurse["id"], {})
        fixed_wd = nurse.get("fixed_weekly_off")

        for i in range(28):
            d = start + timedelta(days=i)
            wd_idx = d.weekday()
            day = i + 1
            shift = shifts.get(day, "")
            is_fixed = (fixed_wd is not None and wd_idx == fixed_wd)
            if not shift and is_fixed:
                shift = "주"
            row_data.append(shift)

        sub_at = submitted_at_map.get(nurse["id"], "")
        if sub_at:
            try:
                sub_at = datetime.fromisoformat(sub_at).strftime("%Y-%m-%d %H:%M")
            except Exception:
                pass
        row_data.append(sub_at or "미제출")
        ws.append(row_data)

        # 셀 스타일
        row_idx = ws.max_row
        for col in range(4, 4 + 28):
            cell = ws.cell(row=row_idx, column=col)
            day = col - 3
            d = start + timedelta(days=day - 1)
            wd_idx = d.weekday()
            is_fixed = (fixed_wd is not None and wd_idx == fixed_wd)
            shift = shifts.get(day, "")
            if is_fixed and not shift:
                cell.fill = gray_fill
            elif cell.value and cell.value != "주":
                cell.fill = yellow_fill
                cell.font = bold_font

    # 열 너비 조정
    ws.column_dimensions["A"].width = 10
    ws.column_dimensions["B"].width = 10
    ws.column_dimensions["C"].width = 8
    for col in range(4, 4 + 28):
        ws.column_dimensions[ws.cell(1, col).column_letter].width = 7
    ws.column_dimensions[ws.cell(1, 4 + 28).column_letter].width = 18

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)

    from urllib.parse import quote
    filename = f"신청현황_{period['start_date']}.xlsx"
    encoded = quote(filename, safe='')
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{encoded}"},
    )
