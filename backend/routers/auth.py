"""인증 라우터"""
from fastapi import APIRouter, HTTPException, Depends, Response
from ..database import get_db, db_nurses
from ..auth import verify_password, hash_password, create_admin_token, create_nurse_token
from ..deps import get_current_nurse, get_current_admin
from ..schemas import (
    AdminLoginRequest, NurseLoginRequest, LoginResponse,
    PinChangeRequest, AdminPwChangeRequest,
)
from ..config import settings

router = APIRouter(prefix="/auth", tags=["인증"])

_IS_PROD = settings.environment == "production"

def _set_auth_cookie(response: Response, token: str, max_age: int) -> None:
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        secure=_IS_PROD,
        samesite="none" if _IS_PROD else "lax",
        max_age=max_age,
        path="/",
    )


@router.post("/admin/login", response_model=LoginResponse)
def admin_login(body: AdminLoginRequest, response: Response):
    db = get_db()
    res = db.table("departments").select("*").eq("id", settings.department_id).single().execute()
    hospital = res.data
    if not hospital:
        raise HTTPException(404, "병원 정보를 찾을 수 없습니다.")
    if not verify_password(body.password, hospital["admin_pw_hash"]):
        raise HTTPException(401, "비밀번호가 틀렸습니다.")
    token = create_admin_token(settings.department_id)
    _set_auth_cookie(response, token, settings.admin_token_expire_hours * 3600)
    return LoginResponse(role="admin", name="관리자")


@router.post("/nurse/login", response_model=LoginResponse)
def nurse_login(body: NurseLoginRequest, response: Response):
    db = get_db()
    res = db_nurses(db).eq("id", body.nurse_id).single().execute()
    nurse = res.data
    if not nurse:
        raise HTTPException(404, "간호사를 찾을 수 없습니다.")
    if not verify_password(body.pin, nurse["pin_hash"]):
        raise HTTPException(401, "PIN이 틀렸습니다.")
    token = create_nurse_token(nurse["id"], nurse["name"])
    _set_auth_cookie(response, token, settings.nurse_token_expire_hours * 3600)
    return LoginResponse(role="nurse", name=nurse["name"], nurse_id=nurse["id"])


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie(
        key="access_token",
        httponly=True,
        secure=_IS_PROD,
        samesite="none" if _IS_PROD else "lax",
        path="/",
    )
    return {"message": "로그아웃되었습니다."}


@router.put("/nurse/pin")
def change_nurse_pin(body: PinChangeRequest, current: dict = Depends(get_current_nurse)):
    db = get_db()
    nurse_id = current["sub"]
    res = db_nurses(db).eq("id", nurse_id).single().execute()
    nurse = res.data
    if not nurse:
        raise HTTPException(404, "간호사를 찾을 수 없습니다.")
    if not verify_password(body.old_pin, nurse["pin_hash"]):
        raise HTTPException(401, "현재 PIN이 틀렸습니다.")
    db_nurses(db).update({"pin_hash": hash_password(body.new_pin)}).eq("id", nurse_id).execute()
    return {"message": "PIN이 변경되었습니다."}


@router.put("/admin/password")
def change_admin_password(body: AdminPwChangeRequest, _: dict = Depends(get_current_admin)):
    db = get_db()
    res = db.table("departments").select("*").eq("id", settings.department_id).single().execute()
    hospital = res.data
    if not verify_password(body.old_pw, hospital["admin_pw_hash"]):
        raise HTTPException(401, "현재 비밀번호가 틀렸습니다.")
    db.table("departments").update({"admin_pw_hash": hash_password(body.new_pw)}).eq("id", settings.department_id).execute()  # noqa
    return {"message": "비밀번호가 변경되었습니다."}


@router.put("/admin/pin-reset/{nurse_id}")
def reset_nurse_pin(nurse_id: str, _: dict = Depends(get_current_admin)):
    """관리자가 특정 간호사 PIN을 0000으로 초기화"""
    db = get_db()
    db_nurses(db).update({"pin_hash": hash_password("0000")}).eq("id", nurse_id).execute()
    return {"message": "PIN이 초기화되었습니다."}
