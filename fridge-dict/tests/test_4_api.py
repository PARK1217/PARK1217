"""REST 동작: 추가·수정·거절, 사람별 즐겨찾기, 공용 배율, 식단 기록, 이력."""
import datetime as dt

USER_A = {"Cf-Access-Authenticated-User-Email": "a@example.com"}
USER_B = {"Cf-Access-Authenticated-User-Email": "b@example.com"}


def test_create_recipe_and_read_back(client, recipe_payload):
    r = client.post("/api/recipes", json=recipe_payload)
    assert r.status_code == 201, r.text
    assert r.json()["id"] == "test-gyeran-mari"
    ids = [x["id"] for x in client.get("/api/recipes").json()]
    assert ids[-1] == "test-gyeran-mari" and len(ids) == 25
    assert client.get("/api/recipes/test-gyeran-mari").json()["name"] == "테스트 계란말이"
    # 같은 id 다시 → 409
    assert client.post("/api/recipes", json=recipe_payload).status_code == 409


def test_create_rejects_unitless_measurements(client, recipe_payload):
    p = dict(recipe_payload, id="test-bad-units", html="<p>고추장 2 · 간장 1 · 설탕 1</p>")
    r = client.post("/api/recipes", json=p)
    assert r.status_code == 400
    body = r.json()
    assert "단위가 없습니다" in body["detail"]
    assert any("고추장 2" in e for e in body["errors"])
    assert client.get("/api/recipes/test-bad-units").status_code == 404


def test_create_rejects_three_tags(client, recipe_payload):
    p = dict(recipe_payload, id="test-three-tags", tags=["달걀", "두부", "치즈"])
    r = client.post("/api/recipes", json=p)
    assert r.status_code == 400
    assert any("최대 2개" in e for e in r.json()["errors"])


def test_unknown_field_rejected(client, recipe_payload):
    p = dict(recipe_payload, id="test-extra", calories=300)
    assert client.post("/api/recipes", json=p).status_code == 422


def test_update_records_history(client):
    before = client.get("/api/recipes/test-gyeran-mari").json()
    r = client.put("/api/recipes/test-gyeran-mari", json={"gist": "수정된 요약", "time": "12분"})
    assert r.status_code == 200
    assert r.json()["gist"] == "수정된 요약" and r.json()["time"] == "12분"
    # 잘못된 patch는 거절, 기존 값 유지
    bad = client.put("/api/recipes/test-gyeran-mari", json={"html": "<p>간장 2 · 설탕 1</p>"})
    assert bad.status_code == 400
    assert client.get("/api/recipes/test-gyeran-mari").json()["gist"] == "수정된 요약"
    hist = client.get("/api/history", params={"kind": "recipe", "id": "test-gyeran-mari"}).json()
    assert [h["action"] for h in hist] == ["update", "create"]
    assert hist[0]["data"]["gist"] == before["gist"]
    assert hist[0]["source"] == "web"
    assert client.put("/api/recipes/nope", json={"gist": "x"}).status_code == 404


def test_swap_crud(client):
    p = {"id": "test-swap", "name": "테스트 대체", "category": "재료 대체", "tags": ["양념"],
         "added": "2026-10-22", "gist": "요약", "html": "<ul><li>간장 1큰술로 대신.</li></ul>"}
    assert client.post("/api/swaps", json=p).status_code == 201
    assert len(client.get("/api/swaps").json()) == 22
    # 레시피 id와 겹치는 id는 거절
    assert client.post("/api/swaps", json=dict(p, id="test-gyeran-mari")).status_code == 409
    assert client.put("/api/swaps/test-swap", json={"category": "손질·보관"}).json()["category"] == "손질·보관"


def test_state_favs_per_user_scale_shared(client):
    assert client.get("/api/state", headers=USER_A).json() == {"favs": [], "scale": 1.5}
    r = client.put("/api/state", headers=USER_A, json={"favs": ["rabokki", "budae-jjigae", "no-such-id"], "scale": 2})
    assert r.json() == {"favs": ["budae-jjigae", "rabokki"], "scale": 2.0}
    # B는 즐겨찾기가 따로, 배율은 공용
    assert client.get("/api/state", headers=USER_B).json() == {"favs": [], "scale": 2.0}
    client.put("/api/state", headers=USER_B, json={"favs": ["rabokki"]})
    assert client.get("/api/state", headers=USER_A).json()["favs"] == ["budae-jjigae", "rabokki"]
    # favs만 바꾸면 scale은 그대로
    client.put("/api/state", headers=USER_A, json={"favs": []})
    assert client.get("/api/state", headers=USER_A).json() == {"favs": [], "scale": 2.0}
    # 헤더 없으면 DEV_USER_EMAIL
    assert client.get("/api/state").json()["favs"] == []
    assert client.put("/api/state", json={"scale": 0}).status_code == 422


def test_meal_log(client):
    today = dt.date.today()
    old = (today - dt.timedelta(days=20)).isoformat()
    r1 = client.post("/api/log", json={"date": today.isoformat(), "name": "라볶이", "comp": ["탄수화물"]})
    assert r1.status_code == 201
    r2 = client.post("/api/log", json={"date": old, "name": "옛날 기록", "comp": []})
    assert r2.status_code == 201
    names = [e["name"] for e in client.get("/api/log", params={"days": 14}).json()]
    assert names == ["라볶이"]
    names = [e["name"] for e in client.get("/api/log", params={"days": 30}).json()]
    assert names == ["옛날 기록", "라볶이"]
    assert client.post("/api/log", json={"date": "오늘", "name": "x", "comp": []}).status_code == 400
    assert client.post("/api/log", json={"date": today.isoformat(), "name": "x", "comp": ["비타민"]}).status_code == 400
    assert client.delete(f"/api/log/{r1.json()['id']}").status_code == 204
    assert client.delete(f"/api/log/{r1.json()['id']}").status_code == 404
    assert client.get("/api/log", params={"days": 14}).json() == []


def test_static_and_legacy_served(client):
    assert client.get("/api/health").json() == {"ok": True}
    assert client.get("/legacy/").status_code == 200
