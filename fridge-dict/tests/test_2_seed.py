"""legacy 24·21건이 DB에 그대로 들어갔는지."""
import json
from pathlib import Path

from app.db import SessionLocal
from app.seed import seed

ROOT = Path(__file__).resolve().parent.parent


def test_seeded_counts(client):
    assert len(client.get("/api/recipes").json()) == 24
    assert len(client.get("/api/swaps").json()) == 21


def test_seeded_content_identical(client):
    for path, url in (("data/recipes.json", "/api/recipes"), ("data/swaps.json", "/api/swaps")):
        file_items = json.loads((ROOT / path).read_text("utf-8"))
        api_items = client.get(url).json()
        assert [i["id"] for i in api_items] == [i["id"] for i in file_items], "순서 또는 id 불일치"
        for f, a in zip(file_items, api_items):
            assert a == f, f"{f['id']} 내용이 파일과 다름"


def test_seed_is_idempotent(client):
    with SessionLocal() as s:
        counts = seed(s, log=lambda *_: None)
    assert counts == {"recipe": 0, "swap": 0}
    assert len(client.get("/api/recipes").json()) == 24
