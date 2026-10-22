"""환경변수 → 설정. 하드코딩 금지 항목(포트·도메인·DB 경로)은 전부 여기서 읽는다."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

PORT = int(os.getenv("PORT", "8080"))
APP_DOMAIN = os.getenv("APP_DOMAIN", "")
DB_PATH = Path(os.getenv("DB_PATH", str(ROOT / "db" / "fridge.db")))
DATA_DIR = Path(os.getenv("DATA_DIR", str(ROOT / "data")))
STATIC_DIR = ROOT / "static"
LEGACY_DIR = ROOT / "legacy"

# Cloudflare Access가 넣어주는 헤더. 로컬에서는 없으므로 DEV_USER_EMAIL로 대신한다.
USER_HEADER = "Cf-Access-Authenticated-User-Email"
DEV_USER_EMAIL = os.getenv("DEV_USER_EMAIL", "local@dev")

DEFAULT_SCALE = 1.5
