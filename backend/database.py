"""Supabase 클라이언트 + 공통 쿼리 헬퍼
요청마다 새 클라이언트를 생성해 idle 후 HTTP/2 연결 종료(RemoteProtocolError) 문제를 방지.
create_client()는 객체 생성만 하고 실제 연결은 execute() 시점에 맺히므로 비용이 거의 없음.
"""
from supabase import create_client, Client
from .config import settings


def get_db() -> Client:
    return create_client(settings.supabase_url, settings.supabase_service_key)


# ── 쿼리 래퍼 ─────────────────────────────────────────────────────────
# supabase-py 2.x: .table() 직후 .eq() 불가 — 반드시 select/update/delete 먼저 호출 필요.
# TableHelper가 department_id 필터를 자동 주입하면서 콜사이트 변경 없이 동작.

class _TableHelper:
    def __init__(self, db: Client, table: str, department_id: str):
        self._db = db
        self._table = table
        self._hid = department_id

    def _sel(self, cols: str = "*"):
        return self._db.table(self._table).select(cols).eq("department_id", self._hid)

    # SELECT 계열
    def select(self, cols: str = "*"):
        return self._sel(cols)

    def eq(self, col: str, val):
        return self._sel().eq(col, val)

    def order(self, col: str, **kwargs):
        return self._sel().order(col, **kwargs)

    def single(self):
        return self._sel().single()

    def execute(self):
        return self._sel().execute()

    def limit(self, count: int):
        return self._sel().limit(count)

    # UPDATE / DELETE 계열
    def update(self, data: dict):
        return self._db.table(self._table).update(data).eq("department_id", self._hid)

    def delete(self):
        return self._db.table(self._table).delete().eq("department_id", self._hid)


# ── 헬퍼 ──────────────────────────────────────────────────────────────

def db_nurses(db: Client) -> _TableHelper:
    return _TableHelper(db, "nurses", settings.department_id)


def db_rules(db: Client) -> _TableHelper:
    return _TableHelper(db, "rules", settings.department_id)


def db_periods(db: Client) -> _TableHelper:
    return _TableHelper(db, "periods", settings.department_id)


def get_active_period(db: Client) -> dict | None:
    """is_active=True인 period 반환. 없으면 가장 최근 period 반환"""
    res = db_periods(db).select("*").execute()
    if not res.data:
        return None
    active = next((p for p in res.data if p.get("is_active")), None)
    if active:
        return active
    # fallback: is_active 미설정 환경 대비
    return max(res.data, key=lambda p: p["start_date"])


def get_period_by_id(db: Client, period_id: str) -> dict | None:
    res = db.table("periods").select("*").eq("id", period_id).single().execute()
    return res.data


def get_period_by_start_date(db: Client, start_date: str) -> dict | None:
    res = (
        db_periods(db)
        .eq("start_date", start_date)
        .execute()
    )
    return res.data[0] if res.data else None
