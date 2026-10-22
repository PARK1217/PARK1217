"""해볼 것 · 메모 · 계획 · 삭제와 복구 · 사진 · 내보내기 · 마지막으로 만든 날."""
import datetime as dt
import struct
import zlib

USER = {"Cf-Access-Authenticated-User-Email": "a@example.com"}


def tiny_png() -> bytes:
    raw = b"\x00\xff\x00\x00"  # 1픽셀, 필터 0 + RGB
    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")


def test_ideas_crud(client):
    r = client.post("/api/ideas", json={"name": "제육볶음", "note": "라면사리 항목에서 언급"})
    assert r.status_code == 201 and r.json()["done_at"] is None
    iid = r.json()["id"]
    assert client.post("/api/ideas", json={"name": " "}).status_code == 400
    assert client.post("/api/ideas", json={"name": "x", "kind": "weird"}).status_code == 400
    assert client.put(f"/api/ideas/{iid}", json={"done": True}).json()["done_at"]
    rows = client.get("/api/ideas").json()
    assert rows[-1]["id"] == iid  # 완료된 건 뒤로
    assert all(i["done_at"] is None for i in client.get("/api/ideas", params={"include_done": "false"}).json())
    assert client.put(f"/api/ideas/{iid}", json={"done": False, "note": "다음 주"}).json()["note"] == "다음 주"
    assert client.delete(f"/api/ideas/{iid}").status_code == 204
    assert client.delete(f"/api/ideas/{iid}").status_code == 404


def test_notes(client):
    r = client.post("/api/notes", json={"kind": "recipe", "item_id": "rabokki", "text": "설탕 줄이니 나았다"}, headers=USER)
    assert r.status_code == 201 and r.json()["user_email"] == "a@example.com"
    assert client.post("/api/notes", json={"kind": "recipe", "item_id": "nope", "text": "x"}).status_code == 404
    assert client.post("/api/notes", json={"kind": "recipe", "item_id": "rabokki", "text": " "}).status_code == 400
    rows = client.get("/api/notes", params={"kind": "recipe", "id": "rabokki"}).json()
    assert [n["text"] for n in rows] == ["설탕 줄이니 나았다"]
    assert client.delete(f"/api/notes/{rows[0]['id']}").status_code == 204
    assert client.get("/api/notes", params={"kind": "recipe", "id": "rabokki"}).json() == []


def test_plan(client):
    today = dt.date.today()
    monday = today - dt.timedelta(days=today.weekday())
    r = client.post("/api/plan", json={"date": monday.isoformat(), "name": "", "recipe_id": "budae-jjigae"})
    assert r.status_code == 201 and r.json()["name"] == "부대찌개"
    r2 = client.post("/api/plan", json={"date": (monday + dt.timedelta(days=2)).isoformat(), "name": "외식"})
    assert r2.status_code == 201 and r2.json()["recipe_id"] is None
    assert client.post("/api/plan", json={"date": "x", "name": "y"}).status_code == 400
    assert client.post("/api/plan", json={"date": monday.isoformat(), "name": "", "recipe_id": "nope"}).status_code == 404
    names = [p["name"] for p in client.get("/api/plan").json()]
    assert names == ["부대찌개", "외식"]
    assert client.delete(f"/api/plan/{r.json()['id']}").status_code == 204
    assert client.delete(f"/api/plan/{r2.json()['id']}").status_code == 204


def test_last_cooked_and_log_recipe_id(client):
    today = dt.date.today().isoformat()
    old = (dt.date.today() - dt.timedelta(days=40)).isoformat()
    a = client.post("/api/log", json={"date": old, "name": "라볶이", "comp": ["탄수화물"]}).json()        # 이름으로 매칭
    b = client.post("/api/log", json={"date": today, "name": "부대찌개", "comp": [], "recipe_id": "budae-jjigae"}).json()
    assert b["recipe_id"] == "budae-jjigae"
    c = client.post("/api/log", json={"date": today, "name": "x", "comp": [], "recipe_id": "nope"}).json()
    assert c["recipe_id"] is None
    last = client.get("/api/log/last").json()
    assert last["rabokki"] == old and last["budae-jjigae"] == today
    for e in (a, b, c):
        client.delete(f"/api/log/{e['id']}")


def test_photo_upload_and_delete(client):
    r = client.post("/api/recipes/rabokki/photo", files={"file": ("p.png", tiny_png(), "image/png")})
    assert r.status_code == 200, r.text
    url = r.json()["photo"]
    assert url == "/photos/rabokki.png"
    assert client.get(url).status_code == 200
    assert client.get("/api/recipes/rabokki").json()["photo"].startswith("/photos/rabokki.png?v=")
    assert client.post("/api/recipes/rabokki/photo", files={"file": ("p.txt", b"hello", "text/plain")}).status_code == 400
    assert client.post("/api/recipes/nope/photo", files={"file": ("p.png", tiny_png(), "image/png")}).status_code == 404
    assert client.delete("/api/recipes/rabokki/photo").status_code == 204
    assert "photo" not in client.get("/api/recipes/rabokki").json()


def test_delete_recipe_and_restore(client, recipe_payload):
    p = dict(recipe_payload, id="to-delete")
    assert client.post("/api/recipes", json=p).status_code == 201
    client.put("/api/state", json={"favs": ["to-delete"]})
    assert client.delete("/api/recipes/to-delete").status_code == 204
    assert client.get("/api/recipes/to-delete").status_code == 404
    assert "to-delete" not in client.get("/api/state").json()["favs"]
    assert client.delete("/api/recipes/to-delete").status_code == 404
    h = client.get("/api/history", params={"id": "to-delete"}).json()[0]
    assert h["action"] == "delete" and h["data"]["name"] == recipe_payload["name"]
    # 되돌리기 → 다시 생긴다
    assert client.post(f"/api/history/{h['id']}/revert").status_code == 200
    assert client.get("/api/recipes/to-delete").json()["gist"] == recipe_payload["gist"]
    client.delete("/api/recipes/to-delete")


def test_spicy_field(client, recipe_payload):
    assert client.get("/api/recipes/rabokki").json()["spicy"] == "매움"
    p = dict(recipe_payload, id="spicy-bad", spicy="아주매움")
    r = client.post("/api/recipes", json=p)
    assert r.status_code == 400 and any("spicy" in e for e in r.json()["errors"])
    assert client.put("/api/recipes/rabokki", json={"spicy": "조절 가능"}).json()["spicy"] == "조절 가능"
    client.put("/api/recipes/rabokki", json={"spicy": "매움"})


def test_export(client):
    data = client.get("/api/export").json()
    assert set(data) >= {"exported_at", "recipes", "swaps", "log", "ideas", "notes", "plan", "settings"}
    assert len(data["recipes"]) >= 24 and len(data["swaps"]) >= 21
    meta = client.get("/api/meta").json()
    assert meta["spicy"] == ["안 매움", "조절 가능", "매움"] and meta["pot_limit_ml"] == 2000
