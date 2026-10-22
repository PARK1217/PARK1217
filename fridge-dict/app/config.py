"""환경변수 → 설정. 하드코딩 금지 항목(포트·도메인·DB 경로)은 전부 여기서 읽는다."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

PORT = int(os.getenv("PORT", "8080"))
APP_DOMAIN = os.getenv("APP_DOMAIN", "")
DB_PATH = Path(os.getenv("DB_PATH", str(ROOT / "db" / "fridge.db")))
DATA_DIR = Path(os.getenv("DATA_DIR", str(ROOT / "data")))
# 레시피 사진. 기본은 DB 파일 옆 photos/ (같은 볼륨이라 같이 백업된다)
PHOTO_DIR = Path(os.getenv("PHOTO_DIR", str(DB_PATH.parent / "photos")))
PHOTO_MAX_BYTES = 6 * 1024 * 1024
POT_LIMIT_ML = int(os.getenv("POT_LIMIT_ML", "2000"))  # 집 냄비 최대 용량
STATIC_DIR = ROOT / "static"
LEGACY_DIR = ROOT / "legacy"

# Cloudflare Access가 넣어주는 헤더. 로컬에서는 없으므로 DEV_USER_EMAIL로 대신한다.
USER_HEADER = "Cf-Access-Authenticated-User-Email"
DEV_USER_EMAIL = os.getenv("DEV_USER_EMAIL", "local@dev")

DEFAULT_SCALE = 1.5

# MCP 엔드포인트는 /mcp/<MCP_SECRET> 에 붙는다. 비어 있거나 짧으면 MCP를 켜지 않는다.
# 생성: python -c "import secrets; print(secrets.token_urlsafe(32))"
MCP_SECRET = os.getenv("MCP_SECRET", "").strip()
MCP_MIN_SECRET_LEN = 32
MCP_ENABLED = len(MCP_SECRET) >= MCP_MIN_SECRET_LEN and MCP_SECRET.replace("-", "").replace("_", "").isalnum()
MCP_PATH = f"/mcp/{MCP_SECRET}" if MCP_ENABLED else ""
