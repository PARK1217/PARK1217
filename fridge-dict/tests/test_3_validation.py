"""계량 표기 검사와 스키마 규칙. MCP도 같은 함수를 쓰므로 여기서 꼼꼼히 본다."""
import json
from pathlib import Path

import pytest

from app.validation import check_measurements, validate_recipe, validate_swap

ROOT = Path(__file__).resolve().parent.parent


@pytest.mark.parametrize("html", [
    "<p>고추장 2 · 간장 1 · 설탕 1</p>",
    "<p>간장 3큰술 · 물엿 4 · 설탕 1큰술</p>",
    "<li>다진 마늘 1, 참기름 1작은술</li>",
    "<p>양념: 고추장 2.</p>",
])
def test_unitless_rejected(html):
    errs = check_measurements(html)
    assert errs, html
    assert "단위가 없습니다" in errs[0]


def test_error_names_the_item():
    errs = check_measurements("<p>고추장 2 · 간장 1큰술</p>")
    assert len(errs) == 1
    assert "고추장 2" in errs[0]


@pytest.mark.parametrize("html", [
    "<p>간장 3큰술 · 물엿 4큰술 · 설탕 1큰술 · 고춧가루 2큰술</p>",
    "<li>전분물(전분 1 : 물 2큰술)을 조금씩.</li>",      # 비율
    "<li>물과 달걀을 1:1로.</li>",                        # 비율
    "<li>재료가 2/3만 잠기게 붓고 센 불.</li>",            # 분수+조사
    "<li>중불 3분, 200도 10~12분, 1~2mm로 썰기.</li>",    # 시간·온도·크기
    "<li>루 6칸(6접시분)에 물 850ml. 3칸만 있으면 500~550ml.</li>",
    "<li>달걀 3개 + 물 150ml. 대파 2대, 깻잎 10장과 함께.</li>",
    "<li>40% 이상, 13~15%, 830ml짜리.</li>",
    "<li>식초 3~4방울, 소금 한 꼬집.</li>",
])
def test_valid_notation_passes(html):
    assert check_measurements(html) == [], html


def test_legacy_measurement_check_has_no_false_positives():
    """오탐 방지: legacy 45건이 모두 통과해야 한다 (원문의 표기 오류 2곳은 extract 스크립트의 FIXES로 고쳤다)."""
    bad = {}
    for fname in ("recipes.json", "swaps.json"):
        for it in json.loads((ROOT / "data" / fname).read_text("utf-8")):
            errs = check_measurements(it["html"])
            if errs:
                bad[it["id"]] = errs
    assert bad == {}


def test_fixes_applied_to_data():
    """2026-10-22 수정 4건이 data/*.json에 반영되어 있는지."""
    recipes = {r["id"]: r for r in json.loads((ROOT / "data/recipes.json").read_text("utf-8"))}
    swaps = {s["id"]: s for s in json.loads((ROOT / "data/swaps.json").read_text("utf-8"))}
    assert recipes["samgyeopsal-curry"]["tags"] == ["돼지고기", "감자"]
    assert recipes["budae-jjigae"]["tags"] == ["가공식품", "김치"]
    assert "양파 ½개·대파를" in recipes["budae-jjigae"]["html"]
    assert "식초 2큰술 · 설탕 1큰술" in swaps["too-much-soaked-miyeok"]["html"]


def test_legacy_items_pass_full_validation():
    """시드 데이터 45건 전체가 엄격 검증(태그 2개 포함)을 통과한다."""
    recipes = json.loads((ROOT / "data/recipes.json").read_text("utf-8"))
    swaps = json.loads((ROOT / "data/swaps.json").read_text("utf-8"))
    failures = {}
    for r in recipes:
        errs = validate_recipe(r)
        if errs:
            failures[r["id"]] = errs
    for s in swaps:
        errs = validate_swap(s)
        if errs:
            failures[s["id"]] = errs
    assert failures == {}


def test_schema_rules(recipe_payload):
    p = dict(recipe_payload)
    p.update(id="Bad Id", category="없는분류", tags=["달걀", "두부", "치즈"], comp=["비타민"], anchor={"n": "달걀", "a": 0, "u": "컵"}, added="22/10/2026")
    errs = validate_recipe(p)
    joined = "\n".join(errs)
    for needle in ("kebab-case", "category", "최대 2개", "comp", "anchor.a", "anchor.u", "YYYY-MM-DD"):
        assert needle in joined, needle


def test_swap_rules():
    errs = validate_swap({"id": "x", "name": "", "category": "재료 대체", "tags": ["닭고기"], "added": "2026-01-01", "gist": "", "html": ""})
    joined = "\n".join(errs)
    for needle in ("name", "tags", "gist", "html"):
        assert needle in joined, needle
