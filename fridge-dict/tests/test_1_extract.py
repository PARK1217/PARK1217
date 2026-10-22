"""data/*.json이 legacy에서 추출한 결과와 글자 단위로 같은지."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
NODE = shutil.which("node") or "/opt/node22/bin/node"


def test_counts_in_files():
    recipes = json.loads((ROOT / "data/recipes.json").read_text("utf-8"))
    swaps = json.loads((ROOT / "data/swaps.json").read_text("utf-8"))
    assert len(recipes) == 24
    assert len(swaps) == 21
    ids = [r["id"] for r in recipes] + [s["id"] for s in swaps]
    assert len(ids) == len(set(ids)), "id가 겹침"


@pytest.mark.skipif(not Path(NODE).exists(), reason="node 없음")
def test_json_matches_legacy():
    r = subprocess.run([NODE, "scripts/extract_legacy.mjs", "--check"], cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
