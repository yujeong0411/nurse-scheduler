"""FastAPI 인증 의존성"""
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from .auth import decode_token

bearer = HTTPBearer(auto_error=False)


def _get_payload(credentials: HTTPAuthorizationCredentials | None) -> dict:
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="인증이 필요합니다.")
    return decode_token(credentials.credentials)


def get_current_admin(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)) -> dict:
    payload = _get_payload(credentials)
    if payload.get("role") != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="관리자 권한이 필요합니다.")
    return payload


def get_current_nurse(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)) -> dict:
    payload = _get_payload(credentials)
    if payload.get("role") != "nurse":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="간호사 인증이 필요합니다.")
    return payload


def get_current_any(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)) -> dict:
    """admin 또는 nurse 모두 허용"""
    return _get_payload(credentials)
