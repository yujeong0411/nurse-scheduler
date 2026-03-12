"""JWT 발급/검증 + bcrypt 해시/검증"""
from datetime import datetime, timedelta, timezone
from jose import jwt, JWTError
from passlib.context import CryptContext
from fastapi import HTTPException, status
from .config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain: str) -> str:
    return pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_token(payload: dict, expires_hours: int) -> str:
    data = {**payload, "exp": datetime.now(timezone.utc) + timedelta(hours=expires_hours)}
    return jwt.encode(data, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="토큰이 유효하지 않습니다.",
            headers={"WWW-Authenticate": "Bearer"},
        )


def create_admin_token(department_id: str) -> str:
    return create_token(
        {"sub": department_id, "role": "admin"},
        settings.admin_token_expire_hours,
    )


def create_nurse_token(nurse_id: str, nurse_name: str) -> str:
    return create_token(
        {"sub": nurse_id, "role": "nurse", "name": nurse_name},
        settings.nurse_token_expire_hours,
    )
