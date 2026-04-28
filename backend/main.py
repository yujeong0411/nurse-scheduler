"""FastAPI 앱 진입점"""
import sys
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone, timedelta
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# engine/ 모듈 경로 등록
_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)

from .routers import auth, nurses, rules, settings, requests, schedule, export, holidays

# 보존 기간 (일) — 변경 시 이 값만 수정
_KEEP_DAYS = 180  # 6개월


def _cleanup_old_periods():
    """시작일 기준 KEEP_DAYS 이상 지난 period 삭제 (CASCADE로 연관 데이터 함께 삭제)"""
    try:
        from .database import get_db
        from .config import settings as cfg
        db = get_db()
        cutoff = (datetime.now(timezone.utc) - timedelta(days=_KEEP_DAYS)).date().isoformat()
        db.table("periods").delete().eq("department_id", cfg.department_id).lt("start_date", cutoff).execute()
    except Exception:
        pass  # 정리 실패 시 서버 시작은 계속


@asynccontextmanager
async def lifespan(app: FastAPI):
    _cleanup_old_periods()
    yield


app = FastAPI(title="NurseScheduler API", version="1.0.0", lifespan=lifespan)

# CORS — Vercel 도메인 + 로컬 개발
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:3000",
        "https://nurse-scheduler-yj.vercel.app",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 라우터 등록
app.include_router(auth.router)
app.include_router(nurses.router)
app.include_router(rules.router)
app.include_router(settings.router)
app.include_router(requests.router)
app.include_router(schedule.router)
app.include_router(export.router)
app.include_router(holidays.router)


@app.get("/health")
def health():
    """Render + Supabase keep-alive 핑용"""
    from .database import get_db
    try:
        # Supabase DB도 함께 깨움
        db = get_db()
        db.table("departments").select("id").limit(1).execute()
        db_ok = True
    except Exception:
        db_ok = False
    return {
        "status": "ok",
        "db": db_ok,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
