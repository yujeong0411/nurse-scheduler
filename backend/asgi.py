"""uvicorn 진입점 — backend/ 폴더 안에서 실행용

사용법 (backend/ 폴더 안에서):
    uv run uvicorn asgi:app --reload --port 8000
"""
import sys
import os

# 프로젝트 루트(backend의 부모)를 sys.path에 추가
# → engine/ 접근 + backend를 패키지로 인식
_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)

from backend.main import app  # noqa: E402
