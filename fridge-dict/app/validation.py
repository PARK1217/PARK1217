"""도메인 검증. REST 라우터와 (2단계) MCP 도구가 같은 함수를 쓴다. FastAPI에 의존하지 않는다.

검증 실패는 '무엇이 왜 틀렸는지' 한국어 문장 목록으로 돌려준다. 호출한 쪽(사람이든 Claude든)이 고쳐서 다시 보낼 수 있게.
"""
from __future__ import annotations

import datetime as dt
import re

# legacy TAG_ORDER 그대로. 칩 순서이자 허용값.
TAG_ORDER: dict[str, list[str]] = {
    "recipe": ["닭고기", "돼지고기", "소고기", "해산물", "두부", "달걀", "감자", "떡", "채소", "면", "김치", "건어물", "가공식품", "치즈", "미역"],
    "swap": ["양념", "채소", "김치", "해산물", "유지", "도구", "보관", "면", "가공식품"],
}
# 분류(한 건에 하나). 화면의 분류 선택 순서이자 허용값.
CATEGORY_ORDER: dict[str, list[str]] = {
    "recipe": ["고기", "해산물", "두부·달걀", "감자·채소", "면·떡", "가공식품"],
    "swap": ["재료 대체", "손질·보관", "도구·요령"],
}
COMPS = ["단백질", "채소", "탄수화물", "발효"]
ANCHOR_UNITS = ("g", "ml", "개", "장")
MAX_TAGS = 2
KINDS = ("recipe", "swap")

ID_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_TAG_RE = re.compile(r"<[^>]+>")

# 계량 표기 검사 -------------------------------------------------------------
# 숫자 토큰: 12 · 1.5 · 2/3 · ½ · 1½ · 그리고 범위 "3~4".
_NUM = r"(?:\d+(?:\.\d+)?(?:/\d+)?|\d*[½⅓⅔¼¾])(?:\s*~\s*\d+(?:\.\d+)?)?"
# 앞에 글자·숫자·소수점·비율 기호가 붙어 있지 않은 숫자가, 뒤에 단위 없이
# 나열 구분자(· , + ) ), 문장 끝, 줄 끝으로 이어지면 '단위 없는 계량'으로 본다.
# "전분 1 : 물 2큰술"의 비율 표기는 ':'가 뒤따르므로 걸리지 않는다.
_UNITLESS_RE = re.compile(
    r"(?<![\w.~/:%-])(" + _NUM + r")(?=\s*(?:[·,+)]|\.(?:\s|$)|$))",
    re.MULTILINE,
)
_PREV_WORD_RE = re.compile(r"([가-힣A-Za-z]+)\s*$")


def strip_tags(html: str) -> str:
    return _TAG_RE.sub(" ", html or "")


def check_measurements(html: str) -> list[str]:
    """본문에서 단위 없는 숫자 나열을 찾아 문장으로 돌려준다. 비어 있으면 통과."""
    text = strip_tags(html)
    errors: list[str] = []
    for m in _UNITLESS_RE.finditer(text):
        num = m.group(1).strip()
        prev = _PREV_WORD_RE.search(text[: m.start()])
        name = prev.group(1) if prev else ""
        shown = f"{name} {num}".strip()
        errors.append(
            f"계량 '{shown}'에 단위가 없습니다. 숫자 뒤에 큰술·작은술·g·ml·개 같은 단위를 붙이세요"
            f"(예: {shown}큰술). 비율은 '전분 1 : 물 2큰술'처럼 ':'로 적습니다."
        )
        if len(errors) >= 5:
            break
    return errors


# 스키마 수준 검증 ------------------------------------------------------------
def _is_date(s: str) -> bool:
    try:
        dt.date.fromisoformat(s)
        return True
    except (TypeError, ValueError):
        return False


def _check_common(kind: str, d: dict, strict_tags: bool) -> list[str]:
    e: list[str] = []
    rid = d.get("id")
    if not isinstance(rid, str) or not ID_RE.match(rid):
        e.append(f"id '{rid}'는 영문 소문자·숫자·하이픈(kebab-case)이어야 합니다. 예: spam-kimchi-jjigae")
    if not (d.get("name") or "").strip():
        e.append("name(이름)이 비어 있습니다.")
    cat = d.get("category")
    if cat not in CATEGORY_ORDER[kind]:
        e.append(f"category '{cat}'는 허용값이 아닙니다. 다음 중 하나: {' · '.join(CATEGORY_ORDER[kind])}")
    tags = d.get("tags")
    if not isinstance(tags, list) or not tags:
        e.append("tags(주재료 태그)는 1개 이상이어야 합니다.")
    else:
        bad = [t for t in tags if t not in TAG_ORDER[kind]]
        if bad:
            e.append(f"tags {bad}는 허용값이 아닙니다. 다음 중에서: {' · '.join(TAG_ORDER[kind])}")
        if strict_tags and len(tags) > MAX_TAGS:
            e.append(f"tags는 주재료만 최대 {MAX_TAGS}개입니다 (지금 {len(tags)}개). 곁들임은 빼세요.")
        if len(set(tags)) != len(tags):
            e.append("tags에 같은 값이 두 번 있습니다.")
    if not isinstance(d.get("tools", []), list):
        e.append("tools는 배열이어야 합니다.")
    if not _is_date(d.get("added", "")):
        e.append("added는 YYYY-MM-DD 날짜여야 합니다.")
    if not (d.get("gist") or "").strip():
        e.append("gist(한 줄 요약)가 비어 있습니다. 그 요리의 성패를 가르는 한 가지를 씁니다.")
    html = d.get("html") or ""
    if not html.strip():
        e.append("html(본문)이 비어 있습니다.")
    else:
        e.extend(check_measurements(html))
    return e


def validate_recipe(d: dict, *, strict_tags: bool = True) -> list[str]:
    e = _check_common("recipe", d, strict_tags)
    comp = d.get("comp", [])
    if not isinstance(comp, list):
        e.append("comp는 배열이어야 합니다.")
    else:
        bad = [c for c in comp if c not in COMPS]
        if bad:
            e.append(f"comp {bad}는 허용값이 아닙니다. {' · '.join(COMPS)} 중에서, 그 요리가 한 끼에서 실제로 맡는 역할만.")
        if len(set(comp)) != len(comp):
            e.append("comp에 같은 값이 두 번 있습니다.")
    if not isinstance(d.get("easy", False), bool):
        e.append("easy는 true/false여야 합니다.")
    anc = d.get("anchor")
    if anc is not None:
        if not isinstance(anc, dict):
            e.append("anchor는 {n, a, u} 객체여야 합니다.")
        else:
            if not (anc.get("n") or "").strip():
                e.append("anchor.n(주재료 이름)이 비어 있습니다.")
            a = anc.get("a")
            if not isinstance(a, (int, float)) or isinstance(a, bool) or a <= 0:
                e.append("anchor.a(기준 양)는 0보다 큰 숫자여야 합니다.")
            if anc.get("u") not in ANCHOR_UNITS:
                e.append(f"anchor.u 단위는 {'·'.join(ANCHOR_UNITS)} 중 하나여야 합니다.")
    return e


def validate_swap(d: dict, *, strict_tags: bool = True) -> list[str]:
    return _check_common("swap", d, strict_tags)


def validate(kind: str, d: dict, *, strict_tags: bool = True) -> list[str]:
    if kind == "recipe":
        return validate_recipe(d, strict_tags=strict_tags)
    if kind == "swap":
        return validate_swap(d, strict_tags=strict_tags)
    raise ValueError(f"unknown kind {kind}")


class ValidationError(Exception):
    def __init__(self, errors: list[str]):
        super().__init__("; ".join(errors))
        self.errors = errors
