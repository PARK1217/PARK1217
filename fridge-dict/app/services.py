"""CRUD와 이력 기록. REST 라우터와 (2단계) MCP 도구가 같이 쓴다. HTTP를 모른다."""
from __future__ import annotations

import datetime as dt

from sqlalchemy import func, select
from sqlalchemy.orm import Session

import json
from pathlib import Path

from .config import DEFAULT_SCALE, PHOTO_DIR, PHOTO_MAX_BYTES
from .models import Favorite, History, Idea, MealLog, Note, Plan, Recipe, Setting, Swap
from .validation import COMPS, KINDS, TAG_ORDER, ValidationError, validate

MODEL = {"recipe": Recipe, "swap": Swap}
RECIPE_FIELDS = ("id", "name", "category", "tags", "comp", "tools", "time", "easy", "base", "anchor", "spicy", "added", "gist", "html")
SWAP_FIELDS = ("id", "name", "category", "tags", "tools", "time", "added", "gist", "html")
FIELDS = {"recipe": RECIPE_FIELDS, "swap": SWAP_FIELDS}


class NotFound(Exception):
    pass


class Conflict(Exception):
    pass


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def today_iso() -> str:
    return dt.date.today().isoformat()


def to_dict(kind: str, row) -> dict:
    d = {f: getattr(row, f) for f in FIELDS[kind]}
    if kind == "recipe":
        if d.get("anchor") is None:
            d.pop("anchor")
        d["spicy"] = d.get("spicy") or ""
        p = photo_path(row.id)
        if p is not None:
            d["photo"] = f"/photos/{p.name}?v={int(p.stat().st_mtime)}"
    return d


# ── 사진 (레시피만) ──────────────────────────────────────────────────────────
PHOTO_EXT = {b"\xff\xd8\xff": "jpg", b"\x89PNG": "png", b"RIFF": "webp"}


def photo_path(item_id: str) -> Path | None:
    for ext in ("jpg", "png", "webp"):
        p = PHOTO_DIR / f"{item_id}.{ext}"
        if p.exists():
            return p
    return None


def save_photo(s: Session, item_id: str, data: bytes) -> str:
    if s.get(Recipe, item_id) is None:
        raise NotFound(f"recipe '{item_id}'가 없습니다.")
    if len(data) > PHOTO_MAX_BYTES:
        raise ValidationError([f"사진이 너무 큽니다 ({len(data) // 1024}KB). {PHOTO_MAX_BYTES // 1024 // 1024}MB 이하로."])
    ext = next((e for magic, e in PHOTO_EXT.items() if data.startswith(magic)), None)
    if ext is None:
        raise ValidationError(["JPEG·PNG·WebP 사진만 올릴 수 있습니다."])
    PHOTO_DIR.mkdir(parents=True, exist_ok=True)
    delete_photo(item_id)
    (PHOTO_DIR / f"{item_id}.{ext}").write_bytes(data)
    return f"/photos/{item_id}.{ext}"


def delete_photo(item_id: str) -> bool:
    p = photo_path(item_id)
    if p is None:
        return False
    p.unlink()
    return True


# ── 레시피 / 대체·보관 ───────────────────────────────────────────────────────
def list_items(s: Session, kind: str) -> list[dict]:
    m = MODEL[kind]
    return [to_dict(kind, r) for r in s.scalars(select(m).order_by(m.seq))]


def search_items(s: Session, kind: str, query: str = "", tag: str = "") -> list[dict]:
    """MCP 목록용. 이름·요약·본문에 query가 들어가고, tag가 있으면 그 태그를 가진 것만. id·name·tags·gist만 돌려준다."""
    q = (query or "").strip().lower()
    out = []
    for d in list_items(s, kind):
        if tag and tag not in d["tags"]:
            continue
        if q:
            hay = (d["name"] + " " + d["gist"] + " " + " ".join(d["tags"]) + " " + d.get("category", "") + " " + d["html"]).lower()
            if q not in hay:
                continue
        out.append({"id": d["id"], "name": d["name"], "category": d.get("category"), "tags": d["tags"], "gist": d["gist"]})
    return out


def get_item(s: Session, kind: str, item_id: str) -> dict:
    row = s.get(MODEL[kind], item_id)
    if row is None:
        raise NotFound(f"{kind} '{item_id}'가 없습니다.")
    return to_dict(kind, row)


def _record(s: Session, kind: str, item_id: str, action: str, data: dict, source: str, user: str) -> None:
    s.add(History(kind=kind, item_id=item_id, action=action, data=data, source=source, user_email=user, changed_at=now_iso()))


def create_item(s: Session, kind: str, data: dict, *, source: str, user: str = "", strict_tags: bool = True) -> dict:
    assert kind in KINDS
    errors = validate(kind, data, strict_tags=strict_tags)
    if errors:
        raise ValidationError(errors)
    m = MODEL[kind]
    if s.get(m, data["id"]) is not None:
        raise Conflict(f"id '{data['id']}'가 이미 있습니다. 수정이라면 PUT(update)을 쓰세요.")
    # 같은 id는 레시피·대체 양쪽에서 유일해야 한다 (즐겨찾기가 id 하나로 둘을 가리키므로)
    other = Swap if kind == "recipe" else Recipe
    if s.get(other, data["id"]) is not None:
        raise Conflict(f"id '{data['id']}'는 다른 탭 항목이 쓰고 있습니다. 다른 id를 쓰세요.")
    seq = (s.scalar(select(func.max(m.seq))) or 0) + 1
    row = m(**{f: data.get(f) for f in FIELDS[kind]}, seq=seq, updated_at=now_iso(), source=source)
    s.add(row)
    _record(s, kind, data["id"], "create", to_dict(kind, row), source, user)
    s.commit()
    return to_dict(kind, row)


def update_item(s: Session, kind: str, item_id: str, patch: dict, *, source: str, user: str = "", strict_tags: bool = True) -> dict:
    assert kind in KINDS
    m = MODEL[kind]
    row = s.get(m, item_id)
    if row is None:
        raise NotFound(f"{kind} '{item_id}'가 없습니다.")
    before = to_dict(kind, row)
    merged = dict(before)
    merged.update({k: v for k, v in patch.items() if k != "id"})
    merged["id"] = item_id
    errors = validate(kind, merged, strict_tags=strict_tags)
    if errors:
        raise ValidationError(errors)
    for f in FIELDS[kind]:
        if f != "id":
            setattr(row, f, merged.get(f))
    row.updated_at = now_iso()
    row.source = source
    _record(s, kind, item_id, "update", before, source, user)
    s.commit()
    return to_dict(kind, row)


def delete_item(s: Session, kind: str, item_id: str, *, source: str, user: str = "") -> dict:
    """삭제. 삭제 전 버전을 이력(action=delete)에 남겨 되돌리기로 복구할 수 있다. 즐겨찾기도 함께 지운다."""
    m = MODEL[kind]
    row = s.get(m, item_id)
    if row is None:
        raise NotFound(f"{kind} '{item_id}'가 없습니다.")
    before = to_dict(kind, row)
    before.pop("photo", None)
    _record(s, kind, item_id, "delete", before, source, user)
    for f in s.scalars(select(Favorite).where(Favorite.item_id == item_id)):
        s.delete(f)
    s.delete(row)
    s.commit()
    return before


def list_history(s: Session, kind: str | None = None, item_id: str | None = None, limit: int = 50) -> list[dict]:
    q = select(History).order_by(History.id.desc()).limit(limit)
    if kind:
        q = q.where(History.kind == kind)
    if item_id:
        q = q.where(History.item_id == item_id)
    return [
        {"id": h.id, "kind": h.kind, "item_id": h.item_id, "action": h.action, "data": h.data,
         "source": h.source, "user_email": h.user_email, "changed_at": h.changed_at}
        for h in s.scalars(q)
    ]


def revert_history(s: Session, history_id: int, *, source: str, user: str = "") -> dict:
    """이력 항목에 저장된 버전으로 되돌린다. 되돌리기 자체도 새 이력(update)으로 남는다.
    옛 버전이 지금 규칙(태그 2개)에 안 맞아도 되돌릴 수 있게 태그 수 검사만 푼다."""
    h = s.get(History, history_id)
    if h is None:
        raise NotFound(f"이력 {history_id}가 없습니다.")
    data = dict(h.data or {})
    data.pop("photo", None)
    if s.get(MODEL[h.kind], h.item_id) is None:
        # 삭제된 항목 → 그 버전으로 다시 만든다
        data["id"] = h.item_id
        return create_item(s, h.kind, data, source=source, user=user, strict_tags=False)
    patch = {k: v for k, v in data.items() if k != "id"}
    if h.kind == "recipe" and "anchor" not in data:
        patch["anchor"] = None
    return update_item(s, h.kind, h.item_id, patch, source=source, user=user, strict_tags=False)


# ── 상태: 즐겨찾기(사람별) + 배율(가구 공용) ───────────────────────────────────
def _setting(s: Session, key: str, default: str) -> str:
    st = s.get(Setting, key)
    return st.value if st else default


def _set_setting(s: Session, key: str, value: str) -> None:
    st = s.get(Setting, key)
    if st is None:
        s.add(Setting(key=key, value=value))
    else:
        st.value = value


def get_state(s: Session, user: str) -> dict:
    favs = list(s.scalars(select(Favorite.item_id).where(Favorite.user_email == user).order_by(Favorite.item_id)))
    scale = float(_setting(s, "scale", str(DEFAULT_SCALE)))
    try:
        stock = json.loads(_setting(s, "stock", "[]"))
    except ValueError:
        stock = []
    return {"favs": favs, "scale": scale, "stock": stock}


def put_state(s: Session, user: str, favs: list[str] | None = None, scale: float | None = None, stock: list[str] | None = None) -> dict:
    if favs is not None:
        known = set(s.scalars(select(Recipe.id))) | set(s.scalars(select(Swap.id)))
        wanted = {f for f in favs if f in known}
        for row in s.scalars(select(Favorite).where(Favorite.user_email == user)):
            if row.item_id not in wanted:
                s.delete(row)
            else:
                wanted.discard(row.item_id)
        for item_id in wanted:
            s.add(Favorite(user_email=user, item_id=item_id))
    if scale is not None:
        _set_setting(s, "scale", str(scale))
    if stock is not None:
        allowed = set(TAG_ORDER["recipe"]) | set(TAG_ORDER["swap"])
        _set_setting(s, "stock", json.dumps([t for t in dict.fromkeys(stock) if t in allowed], ensure_ascii=False))
    s.commit()
    return get_state(s, user)


# ── 식단 기록(가구 공용) ─────────────────────────────────────────────────────
def list_log(s: Session, days: int = 14) -> list[dict]:
    days = max(1, min(days, 366))
    since = (dt.date.today() - dt.timedelta(days=days)).isoformat()
    q = select(MealLog).where(MealLog.date >= since).order_by(MealLog.date, MealLog.id)
    return [{"id": r.id, "date": r.date, "name": r.name, "comp": r.comp, "recipe_id": r.recipe_id} for r in s.scalars(q)]


def last_cooked(s: Session) -> dict[str, str]:
    """레시피 id → 마지막으로 먹은 날. recipe_id가 없는 옛 기록은 이름으로 맞춘다."""
    by_name = {r.name: r.id for r in s.scalars(select(Recipe))}
    out: dict[str, str] = {}
    for r in s.scalars(select(MealLog).order_by(MealLog.date)):
        rid = r.recipe_id or by_name.get(r.name)
        if rid:
            out[rid] = r.date
    return out


def add_log(s: Session, date: str, name: str, comp: list[str], recipe_id: str | None = None) -> dict:
    errors = []
    try:
        dt.date.fromisoformat(date)
    except (TypeError, ValueError):
        errors.append("date는 YYYY-MM-DD여야 합니다.")
    if not (name or "").strip():
        errors.append("name(먹은 것)이 비어 있습니다.")
    bad = [c for c in comp if c not in COMPS]
    if bad:
        errors.append(f"comp {bad}는 허용값이 아닙니다. {' · '.join(COMPS)} 중에서.")
    if errors:
        raise ValidationError(errors)
    if recipe_id and s.get(Recipe, recipe_id) is None:
        recipe_id = None
    row = MealLog(date=date, name=name.strip(), comp=list(dict.fromkeys(comp)), recipe_id=recipe_id, created_at=now_iso())
    s.add(row)
    s.commit()
    return {"id": row.id, "date": row.date, "name": row.name, "comp": row.comp, "recipe_id": row.recipe_id}


def delete_log(s: Session, entry_id: int) -> None:
    row = s.get(MealLog, entry_id)
    if row is None:
        raise NotFound(f"기록 {entry_id}가 없습니다.")
    s.delete(row)
    s.commit()


# ── 해볼 것 ─────────────────────────────────────────────────────────────────
def _idea(i: Idea) -> dict:
    return {"id": i.id, "kind": i.kind, "name": i.name, "note": i.note or "", "source": i.source, "created_at": i.created_at, "done_at": i.done_at}


def list_ideas(s: Session, include_done: bool = True) -> list[dict]:
    rows = list(s.scalars(select(Idea).order_by(Idea.id.desc()).limit(200)))
    open_ = [_idea(i) for i in rows if not i.done_at]
    done = [_idea(i) for i in rows if i.done_at] if include_done else []
    return open_ + done


def add_idea(s: Session, name: str, note: str = "", kind: str = "recipe", *, source: str = "web") -> dict:
    errors = []
    if not (name or "").strip():
        errors.append("name(이름)이 비어 있습니다.")
    if kind not in KINDS:
        errors.append("kind는 recipe 또는 swap이어야 합니다.")
    if errors:
        raise ValidationError(errors)
    row = Idea(kind=kind, name=name.strip(), note=(note or "").strip(), source=source, created_at=now_iso())
    s.add(row)
    s.commit()
    return _idea(row)


def update_idea(s: Session, idea_id: int, patch: dict) -> dict:
    row = s.get(Idea, idea_id)
    if row is None:
        raise NotFound(f"해볼 것 {idea_id}가 없습니다.")
    if patch.get("name") is not None:
        if not patch["name"].strip():
            raise ValidationError(["name(이름)이 비어 있습니다."])
        row.name = patch["name"].strip()
    if patch.get("note") is not None:
        row.note = patch["note"].strip()
    if patch.get("kind") is not None:
        if patch["kind"] not in KINDS:
            raise ValidationError(["kind는 recipe 또는 swap이어야 합니다."])
        row.kind = patch["kind"]
    if patch.get("done") is not None:
        row.done_at = now_iso() if patch["done"] else None
    s.commit()
    return _idea(row)


def delete_idea(s: Session, idea_id: int) -> None:
    row = s.get(Idea, idea_id)
    if row is None:
        raise NotFound(f"해볼 것 {idea_id}가 없습니다.")
    s.delete(row)
    s.commit()


# ── 메모 ───────────────────────────────────────────────────────────────────
def _note(n: Note) -> dict:
    return {"id": n.id, "kind": n.kind, "item_id": n.item_id, "text": n.text, "user_email": n.user_email, "created_at": n.created_at}


def list_notes(s: Session, kind: str, item_id: str) -> list[dict]:
    q = select(Note).where(Note.kind == kind, Note.item_id == item_id).order_by(Note.id.desc())
    return [_note(n) for n in s.scalars(q)]


def add_note(s: Session, kind: str, item_id: str, text: str, *, user: str = "") -> dict:
    if kind not in KINDS:
        raise ValidationError(["kind는 recipe 또는 swap이어야 합니다."])
    if s.get(MODEL[kind], item_id) is None:
        raise NotFound(f"{kind} '{item_id}'가 없습니다.")
    if not (text or "").strip():
        raise ValidationError(["메모가 비어 있습니다."])
    row = Note(kind=kind, item_id=item_id, text=text.strip(), user_email=user, created_at=now_iso())
    s.add(row)
    s.commit()
    return _note(row)


def delete_note(s: Session, note_id: int) -> None:
    row = s.get(Note, note_id)
    if row is None:
        raise NotFound(f"메모 {note_id}가 없습니다.")
    s.delete(row)
    s.commit()


# ── 주간 계획 ───────────────────────────────────────────────────────────────
def _plan(pn: Plan) -> dict:
    return {"id": pn.id, "date": pn.date, "name": pn.name, "recipe_id": pn.recipe_id}


def list_plan(s: Session, start: str, end: str) -> list[dict]:
    q = select(Plan).where(Plan.date >= start, Plan.date <= end).order_by(Plan.date, Plan.id)
    return [_plan(pn) for pn in s.scalars(q)]


def add_plan(s: Session, date: str, name: str, recipe_id: str | None = None) -> dict:
    try:
        dt.date.fromisoformat(date)
    except (TypeError, ValueError):
        raise ValidationError(["date는 YYYY-MM-DD여야 합니다."])
    if recipe_id:
        r = s.get(Recipe, recipe_id)
        if r is None:
            raise NotFound(f"recipe '{recipe_id}'가 없습니다.")
        name = r.name
    if not (name or "").strip():
        raise ValidationError(["name(요리 이름)이 비어 있습니다."])
    row = Plan(date=date, name=name.strip(), recipe_id=recipe_id or None, created_at=now_iso())
    s.add(row)
    s.commit()
    return _plan(row)


def delete_plan(s: Session, plan_id: int) -> None:
    row = s.get(Plan, plan_id)
    if row is None:
        raise NotFound(f"계획 {plan_id}가 없습니다.")
    s.delete(row)
    s.commit()


# ── 내보내기 ─────────────────────────────────────────────────────────────────
def export_all(s: Session) -> dict:
    return {
        "exported_at": now_iso(),
        "recipes": list_items(s, "recipe"),
        "swaps": list_items(s, "swap"),
        "log": [{"id": r.id, "date": r.date, "name": r.name, "comp": r.comp, "recipe_id": r.recipe_id} for r in s.scalars(select(MealLog).order_by(MealLog.date, MealLog.id))],
        "ideas": list_ideas(s),
        "notes": [_note(n) for n in s.scalars(select(Note).order_by(Note.id))],
        "plan": [_plan(pn) for pn in s.scalars(select(Plan).order_by(Plan.date, Plan.id))],
        "settings": {k: v for k, v in ((st.key, st.value) for st in s.scalars(select(Setting)))},
    }
