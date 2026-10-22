"""테스트는 임시 SQLite 파일을 쓴다. app 모듈 import 전에 DB_PATH를 바꿔야 한다."""
import os
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

_tmp = Path(os.environ.get("PYTEST_TMPDIR", "/tmp")) / "fridge-dict-test"
shutil.rmtree(_tmp, ignore_errors=True)
_tmp.mkdir(parents=True)
os.environ["DB_PATH"] = str(_tmp / "test.db")
os.environ["DEV_USER_EMAIL"] = "tester@dev"

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


@pytest.fixture(scope="session")
def client():
    # with 블록이 lifespan(테이블 생성 + 시드)을 실행한다
    with TestClient(app) as c:
        yield c


@pytest.fixture
def recipe_payload():
    return {
        "id": "test-gyeran-mari",
        "name": "테스트 계란말이",
        "category": "두부·달걀",
        "tags": ["달걀"],
        "comp": ["단백질"],
        "tools": ["팬"],
        "time": "10분",
        "easy": True,
        "base": "2인분",
        "anchor": {"n": "달걀", "a": 3, "u": "개"},
        "added": "2026-10-22",
        "gist": "약불에서 천천히 말아야 갈라지지 않습니다.",
        "html": "<h3>순서</h3><ol><li>달걀 3개에 소금 ½작은술, 물 1큰술을 풀기.</li><li>약불 3분, 세 번에 나눠 말기.</li></ol>",
    }
