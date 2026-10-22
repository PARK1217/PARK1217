"""data/*.json → DB. 없는 id만 넣으므로 여러 번 실행해도 안전하다.

사용: python -m app.seed   (앱 시작 때도 자동으로 한 번 돈다)
legacy 원문은 그대로 넣고, 검증에 걸리는 항목은 경고만 남긴다.
"""
from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .config import DATA_DIR
from .models import Recipe, Swap
from .services import FIELDS, now_iso
from .validation import validate

FILES = (("recipe", "recipes.json", Recipe), ("swap", "swaps.json", Swap))


def seed(session: Session, data_dir: Path = DATA_DIR, log=print) -> dict[str, int]:
    counts: dict[str, int] = {}
    for kind, fname, model in FILES:
        path = Path(data_dir) / fname
        if not path.exists():
            log(f"[seed] {path} 없음, 건너뜀")
            counts[kind] = 0
            continue
        items = json.loads(path.read_text("utf-8"))
        existing = set(session.scalars(select(model.id)))
        seq = session.scalar(select(func.max(model.seq))) or 0
        added = 0
        for it in items:
            if it["id"] in existing:
                continue
            for msg in validate(kind, it):
                log(f"[seed] 경고 {kind} {it['id']}: {msg}")
            seq += 1
            session.add(model(**{f: it.get(f) for f in FIELDS[kind]}, seq=seq, updated_at=now_iso(), source="seed"))
            added += 1
        session.commit()
        counts[kind] = added
        log(f"[seed] {kind}: 파일 {len(items)}건, 새로 {added}건")
    return counts


if __name__ == "__main__":
    from .db import SessionLocal, init_db

    init_db()
    with SessionLocal() as s:
        seed(s)
