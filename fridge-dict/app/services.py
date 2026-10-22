"""CRUD와 이력 기록. REST 라우터와 (2단계) MCP 도구가 같이 쓴다. HTTP를 모른다."""
from __future__ import annotations

import datetime as dt

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .config import DEFAULT_SCALE
from .models import Favorite, History, MealLog, Recipe, Setting, Swap
from .validation import COMPS, KINDS, ValidationError, validate

MODEL = {"recipe": Recipe, "swap": Swap}
RECIPE_FIELDS = ("id", "name", "category", "tags", "comp", "tools", "time", "easy", "base", "anchor", "added", "gist", "html")
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
    if kind == "recipe" and d.get("anchor") is None:
        d.pop("anchor")
    return d


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


def create_item(s: Session, kind: str, data: dict, *, source: str, user: str = "") -> dict:
    assert kind in KINDS
    errors = validate(kind, data)
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
    patch = {k: v for k, v in data.items() if k != "id"}
    if h.kind == "recipe" and "anchor" not in data:
        patch["anchor"] = None
    return update_item(s, h.kind, h.item_id, patch, source=source, user=user, strict_tags=False)


# ── 상태: 즐겨찾기(사람별) + 배율(가구 공용) ───────────────────────────────────
def get_state(s: Session, user: str) -> dict:
    favs = list(s.scalars(select(Favorite.item_id).where(Favorite.user_email == user).order_by(Favorite.item_id)))
    st = s.get(Setting, "scale")
    scale = float(st.value) if st else DEFAULT_SCALE
    return {"favs": favs, "scale": scale}


def put_state(s: Session, user: str, favs: list[str] | None = None, scale: float | None = None) -> dict:
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
        st = s.get(Setting, "scale")
        if st is None:
            s.add(Setting(key="scale", value=str(scale)))
        else:
            st.value = str(scale)
    s.commit()
    return get_state(s, user)


# ── 식단 기록(가구 공용) ─────────────────────────────────────────────────────
def list_log(s: Session, days: int = 14) -> list[dict]:
    days = max(1, min(days, 366))
    since = (dt.date.today() - dt.timedelta(days=days)).isoformat()
    q = select(MealLog).where(MealLog.date >= since).order_by(MealLog.date, MealLog.id)
    return [{"id": r.id, "date": r.date, "name": r.name, "comp": r.comp} for r in s.scalars(q)]


def add_log(s: Session, date: str, name: str, comp: list[str]) -> dict:
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
    row = MealLog(date=date, name=name.strip(), comp=list(dict.fromkeys(comp)), created_at=now_iso())
    s.add(row)
    s.commit()
    return {"id": row.id, "date": row.date, "name": row.name, "comp": row.comp}


def delete_log(s: Session, entry_id: int) -> None:
    row = s.get(MealLog, entry_id)
    if row is None:
        raise NotFound(f"기록 {entry_id}가 없습니다.")
    s.delete(row)
    s.commit()
