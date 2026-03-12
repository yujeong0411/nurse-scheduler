"""간호사 CRUD + 엑셀 import"""
import io
import sys
import os
import tempfile
from fastapi import APIRouter, HTTPException, UploadFile, File, Depends
from ..database import get_db, db_nurses
from ..auth import hash_password
from ..deps import get_current_admin, get_current_nurse
from ..schemas import NurseCreate, NurseUpdate, NurseOut
from ..config import settings

router = APIRouter(prefix="/nurses", tags=["간호사"])


def _row_to_out(row: dict) -> NurseOut:
    return NurseOut(
        id=row["id"],
        name=row["name"],
        role=row.get("role", ""),
        grade=row.get("grade", ""),
        is_pregnant=row.get("is_pregnant", False),
        is_male=row.get("is_male", False),
        is_4day_week=row.get("is_4day_week", False),
        fixed_weekly_off=row.get("fixed_weekly_off"),
        vacation_days=row.get("vacation_days", 0),
        prev_month_n=row.get("prev_month_n", 0),
        pending_sleep=row.get("pending_sleep", False),
        menstrual_used=row.get("menstrual_used", False),
        prev_tail_shifts=row.get("prev_tail_shifts", []),
        note=row.get("note", ""),
        sort_order=row.get("sort_order", 0),
    )


@router.get("/me", response_model=NurseOut)
def get_my_profile(current: dict = Depends(get_current_nurse)):
    """간호사 본인 프로필 조회 (유효성 검사용)"""
    db = get_db()
    res = db_nurses(db).eq("id", current["sub"]).single().execute()
    if not res.data:
        raise HTTPException(404, "간호사를 찾을 수 없습니다.")
    return _row_to_out(res.data)


@router.get("/names")
def list_nurse_names():
    """이름+ID만 공개 (간호사 로그인 화면용, 인증 불필요)"""
    db = get_db()
    res = db_nurses(db).select("id,name,grade,role").order("sort_order").execute()
    return [{"id": r["id"], "name": r["name"], "grade": r.get("grade",""), "role": r.get("role","")} for r in res.data]


@router.get("", response_model=list[NurseOut])
def list_nurses(_: dict = Depends(get_current_admin)):
    db = get_db()
    res = db_nurses(db).order("sort_order").execute()
    return [_row_to_out(r) for r in res.data]


@router.post("", response_model=NurseOut)
def create_nurse(body: NurseCreate, _: dict = Depends(get_current_admin)):
    db = get_db()
    data = body.model_dump()
    data["department_id"] = settings.department_id
    data["pin_hash"] = hash_password("0000")
    res = db.table("nurses").insert(data).execute()
    return _row_to_out(res.data[0])


@router.put("/{nurse_id}", response_model=NurseOut)
def update_nurse(nurse_id: str, body: NurseUpdate, _: dict = Depends(get_current_admin)):
    db = get_db()
    data = body.model_dump()
    res = db_nurses(db).update(data).eq("id", nurse_id).execute()
    if not res.data:
        raise HTTPException(404, "간호사를 찾을 수 없습니다.")
    return _row_to_out(res.data[0])


@router.delete("/{nurse_id}")
def delete_nurse(nurse_id: str, _: dict = Depends(get_current_admin)):
    db = get_db()
    db_nurses(db).delete().eq("id", nurse_id).execute()
    return {"message": "삭제되었습니다."}


@router.post("/import-excel", response_model=list[NurseOut])
def import_nurses_excel(file: UploadFile = File(...), _: dict = Depends(get_current_admin)):
    """근무표_규칙.xlsx → 간호사 목록 upsert"""
    # engine 경로를 sys.path에 추가
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    if root not in sys.path:
        sys.path.insert(0, root)

    from engine.excel_io import import_nurse_rules

    content = file.file.read()
    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    try:
        engine_nurses = import_nurse_rules(tmp_path)
    except Exception as e:
        raise HTTPException(400, f"엑셀 파싱 실패: {e}")
    finally:
        os.unlink(tmp_path)

    db = get_db()
    # 기존 간호사 이름→UUID 맵
    existing_res = db_nurses(db).execute()
    name_to_id = {r["name"]: r["id"] for r in existing_res.data}

    results = []
    for i, nurse in enumerate(engine_nurses):
        data = {
            "department_id": settings.department_id,
            "name": nurse.name,
            "role": nurse.role,
            "grade": nurse.grade,
            "is_pregnant": nurse.is_pregnant,
            "is_male": nurse.is_male,
            "is_4day_week": nurse.is_4day_week,
            "fixed_weekly_off": nurse.fixed_weekly_off,
            "vacation_days": nurse.vacation_days,
            "prev_month_n": nurse.prev_month_N,
            "note": nurse.note,
            "sort_order": i,
        }
        if nurse.name in name_to_id:
            # 기존 간호사 업데이트 (PIN 유지)
            res = db_nurses(db).update(data).eq("id", name_to_id[nurse.name]).execute()
        else:
            data["pin_hash"] = hash_password("0000")
            res = db.table("nurses").insert(data).execute()
        results.append(_row_to_out(res.data[0]))

    return results
