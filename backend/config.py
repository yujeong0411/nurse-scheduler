from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

_ENV_FILE = Path(__file__).parent / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(_ENV_FILE), env_file_encoding="utf-8")

    supabase_url: str
    supabase_service_key: str   # service_role key (RLS 우회)
    supabase_anon_key: str      # 프론트 keep-alive용 참고값
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    admin_token_expire_hours: int = 8
    nurse_token_expire_hours: int = 24
    department_id: str          # 운영 부서 UUID — Supabase 초기화 시 설정
    environment: str = "development"  # "development" | "production"


settings = Settings()  # type: ignore[call-arg]
