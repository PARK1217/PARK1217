# 냉장고 사전

집에서 쓰는 레시피·대체·보관·식단 기록 웹앱. claude.ai 아티팩트 한 장이던 것을 FastAPI + SQLite로 옮겼다.
두 사람이 폰으로 같이 쓰며, 즐겨찾기는 사람별, 분량 배율과 식단 기록은 가구 공용이다.

- 설계·규칙·결정 기록: [CLAUDE.md](CLAUDE.md)
- 배포 순서: [deploy/README.md](deploy/README.md)

## 로컬 실행

```bash
pip install -r requirements.txt -r requirements-dev.txt
uvicorn app.main:app --reload --port 8080   # 첫 실행 때 data/*.json을 DB로 시드
# http://127.0.0.1:8080/         새 화면
# http://127.0.0.1:8080/legacy/  아티팩트 원본 (비교용)
# http://127.0.0.1:8080/api/docs API 문서
pytest -q
```

Docker:

```bash
cp .env.example .env
docker compose up -d --build
```

## 구조

```
app/        FastAPI. validation.py·services.py는 REST와 (2단계) MCP가 공유
static/     index.html 한 파일. 빌드 없음
data/       recipes.json(24) · swaps.json(21). scripts/extract_legacy.mjs가 legacy에서 생성
legacy/     아티팩트 원본. 수정하지 않는다
tests/      pytest 32개
deploy/     LXC · Docker · Cloudflare Tunnel · Access
```

## 레시피 추가

1. `data/recipes.json`에 항목을 넣고 재시작하면 없는 id만 DB에 들어간다. 또는
2. `POST /api/recipes`로 보낸다. 단위 없는 계량(`고추장 2 · 간장 1`)은 400으로 거절되고 이유가 돌아온다.

규칙은 CLAUDE.md의 '콘텐츠 규칙'을 따른다.
