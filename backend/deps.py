"""FastAPI 인증 의존성"""
from fastapi import Request, HTTPException, status
from .auth import decode_token


def _get_payload(request: Request) -> dict:
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="인증이 필요합니다.")
    return decode_token(token)


def get_current_admin(request: Request) -> dict:
    payload = _get_payload(request)
    if payload.get("role") != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="관리자 권한이 필요합니다.")
    return payload


def get_current_nurse(request: Request) -> dict:
    payload = _get_payload(request)
    if payload.get("role") != "nurse":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="간호사 인증이 필요합니다.")
    return payload


def get_current_any(request: Request) -> dict:
    """admin 또는 nurse 모두 허용"""
    return _get_payload(request)
