"""MCP 엔드포인트: 비밀 경로, 도구 목록, REST와 같은 검증, 이력·되돌리기."""
import json

MCP = "/mcp/test-secret-0123456789abcdefghijklmnopqrstuvwxyz"
HEADERS = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json"}


def rpc(client, method, params=None, rid=1):
    r = client.post(MCP, json={"jsonrpc": "2.0", "id": rid, "method": method, "params": params or {}}, headers=HEADERS)
    assert r.status_code == 200, f"{method}: {r.status_code} {r.text[:300]}"
    body = r.json()
    assert "error" not in body, body
    return body["result"]


def call(client, name, args):
    """(isError, 텍스트, 데이터). 데이터는 structuredContent가 있으면 그것, 없으면 텍스트의 JSON."""
    res = rpc(client, "tools/call", {"name": name, "arguments": args})
    text = "\n".join(c.get("text", "") for c in res.get("content", []) if c.get("type") == "text")
    data = res.get("structuredContent")
    if data is None and text.strip().startswith(("{", "[")):
        try:
            data = json.loads(text)
        except ValueError:
            data = None
    if isinstance(data, dict) and set(data) == {"result"}:
        data = {"result": data["result"]}
    return res.get("isError", False), text, data


def test_wrong_secret_is_404(client):
    r = client.post("/mcp/wrong-secret", json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"}, headers=HEADERS)
    assert r.status_code == 404
    assert client.post("/mcp", json={}, headers=HEADERS).status_code in (404, 405)  # 정적 마운트가 받는다


def test_initialize_and_tool_list(client):
    res = rpc(client, "initialize", {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "t", "version": "0"}})
    assert res["serverInfo"]["name"] == "냉장고 사전"
    assert "계량" in res.get("instructions", "")
    tools = {t["name"]: t for t in rpc(client, "tools/list")["tools"]}
    assert set(tools) == {"list_recipes", "get_recipe", "add_recipe", "update_recipe", "list_swaps", "get_swap", "add_swap", "update_swap", "log_meal", "list_ideas", "add_idea"}
    assert "숫자+단위" in tools["add_recipe"]["description"]
    assert "recipe" in tools["add_recipe"]["inputSchema"]["properties"]


def test_list_and_get(client):
    err, text, data = call(client, "list_recipes", {})
    assert not err
    rows = data["result"] if data else json.loads(text)
    assert len(rows) >= 24 and set(rows[0]) == {"id", "name", "category", "tags", "gist"}
    err, text, data = call(client, "list_recipes", {"query": "쌀뜨물"})
    rows = data["result"]
    assert [r["id"] for r in rows] == ["spam-kimchi-jjigae"]
    err, text, data = call(client, "list_recipes", {"tag": "달걀"})
    assert all("달걀" in r["tags"] for r in data["result"]) and data["result"]
    err, text, data = call(client, "get_recipe", {"id": "rabokki"})
    assert not err and data["html"].startswith("\n<h3>")
    err, text, _ = call(client, "get_recipe", {"id": "nope"})
    assert err and "없습니다" in text


def test_add_recipe_rejects_unitless_then_accepts(client, recipe_payload):
    bad = dict(recipe_payload, id="mcp-test-recipe", html="<p>고추장 2 · 간장 1</p>")
    err, text, _ = call(client, "add_recipe", {"recipe": bad})
    assert err and "단위가 없습니다" in text and "고추장 2" in text
    assert client.get("/api/recipes/mcp-test-recipe").status_code == 404
    good = dict(recipe_payload, id="mcp-test-recipe")
    err, text, data = call(client, "add_recipe", {"recipe": good})
    assert not err, text
    assert data["ok"] is True
    assert client.get("/api/recipes/mcp-test-recipe").json()["name"] == recipe_payload["name"]
    hist = client.get("/api/history", params={"id": "mcp-test-recipe"}).json()
    assert hist[0]["source"] == "mcp" and hist[0]["action"] == "create"
    # 같은 id 다시 → 오류 문장
    err, text, _ = call(client, "add_recipe", {"recipe": good})
    assert err and "이미 있습니다" in text


def test_update_recipe_and_revert_from_web(client):
    err, text, _ = call(client, "update_recipe", {"id": "mcp-test-recipe", "patch": {"gist": "MCP가 고친 요약"}})
    assert not err, text
    assert client.get("/api/recipes/mcp-test-recipe").json()["gist"] == "MCP가 고친 요약"
    hist = client.get("/api/history", params={"id": "mcp-test-recipe"}).json()
    upd = next(h for h in hist if h["action"] == "update")
    assert upd["source"] == "mcp"
    # 웹에서 되돌리기 → 수정 전 요약으로
    r = client.post(f"/api/history/{upd['id']}/revert")
    assert r.status_code == 200, r.text
    assert r.json()["gist"] == upd["data"]["gist"]
    assert client.get("/api/recipes/mcp-test-recipe").json()["gist"] == upd["data"]["gist"]
    hist2 = client.get("/api/history", params={"id": "mcp-test-recipe"}).json()
    assert hist2[0]["action"] == "update" and hist2[0]["source"] == "web" and hist2[0]["data"]["gist"] == "MCP가 고친 요약"
    assert client.post("/api/history/999999/revert").status_code == 404
    # 잘못된 patch는 거절
    err, text, _ = call(client, "update_recipe", {"id": "mcp-test-recipe", "patch": {"tags": ["달걀", "두부", "치즈"]}})
    assert err and "최대 2개" in text


def test_revert_to_old_version_with_three_tags_is_allowed(client):
    """옛 버전이 지금 규칙(태그 2개)에 안 맞아도 되돌리기는 막히지 않아야 한다."""
    from app.db import SessionLocal
    from app.models import History
    from app.services import now_iso

    cur = client.get("/api/recipes/samgyeopsal-curry").json()
    old = dict(cur, tags=["돼지고기", "감자", "채소"], gist="옛 요약")
    with SessionLocal() as s:
        h = History(kind="recipe", item_id="samgyeopsal-curry", action="update", data=old, source="web", user_email="", changed_at=now_iso())
        s.add(h)
        s.commit()
        hid = h.id
    assert client.post(f"/api/history/{hid}/revert").status_code == 200
    got = client.get("/api/recipes/samgyeopsal-curry").json()
    assert got["tags"] == ["돼지고기", "감자", "채소"] and got["gist"] == "옛 요약"
    # 되돌린 뒤 다시 현재 버전으로
    back = client.get("/api/history", params={"id": "samgyeopsal-curry"}).json()[0]
    assert client.post(f"/api/history/{back['id']}/revert").status_code == 200
    assert client.get("/api/recipes/samgyeopsal-curry").json()["tags"] == cur["tags"]


def test_swap_tools_and_log_meal(client):
    err, _, data = call(client, "list_swaps", {"query": "밀키트"})
    assert not err and [r["id"] for r in data["result"]] == ["mealkit-additions"]
    err, _, data = call(client, "get_swap", {"id": "mealkit-additions"})
    assert "<ul>" in data["html"]
    err, text, _ = call(client, "add_swap", {"swap": {"id": "mcp-test-swap", "name": "테스트", "category": "없는분류", "tags": ["양념"], "added": "2026-10-22", "gist": "g", "html": "<p>x</p>"}})
    assert err and "category" in text
    err, text, data = call(client, "add_swap", {"swap": {"id": "mcp-test-swap", "name": "테스트", "category": "재료 대체", "tags": ["양념"], "added": "2026-10-22", "gist": "g", "html": "<p>간장 1큰술</p>"}})
    assert not err and data["ok"]
    err, text, data = call(client, "update_swap", {"id": "mcp-test-swap", "patch": {"gist": "고침"}})
    assert not err and client.get("/api/swaps/mcp-test-swap").json()["gist"] == "고침"
    err, text, data = call(client, "log_meal", {"name": "MCP 저녁", "comp": ["단백질", "채소"]})
    assert not err and data["entry"]["name"] == "MCP 저녁"
    assert any(e["name"] == "MCP 저녁" for e in client.get("/api/log?days=1").json())
    err, text, _ = call(client, "log_meal", {"name": "x", "comp": ["비타민"]})
    assert err and "comp" in text


def test_idea_tools(client):
    err, text, data = call(client, "add_idea", {"name": "오야코동", "note": "닭꼬치 타레 재사용"})
    assert not err and data["ok"] and data["idea"]["source"] == "mcp"
    err, _, data = call(client, "list_ideas", {})
    assert any(i["name"] == "오야코동" for i in data["result"])
    err, text, _ = call(client, "add_idea", {"name": "  ", "note": ""})
    assert err and "name" in text
