# 냉장고 사전

집에서 쓰는 레시피·대체·보관·식단 기록 웹앱. claude.ai 아티팩트 한 장이던 것을 FastAPI + SQLite로 옮겼다.
두 사람이 폰으로 같이 쓰며, 즐겨찾기는 사람별, 분량 배율·냉장고 재고·식단 기록·계획·해볼 것·메모는 가구 공용이다.
레시피 열면 조리 모드(화면 안 꺼짐, 단계 체크), 냄비 용량 경고, 사진, 메모, 편집이 있고, 식단 탭에 주간 계획과 장보기, '해볼 것' 탭에 아직 안 해본 아이디어를 둔다.

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

3. claude.ai 커스텀 커넥터(MCP)로 대화 중 바로 넣는다. `MCP_SECRET`을 두면 `/mcp/<secret>`에 켜진다. 등록 방법은 deploy/README.md 6절.

규칙은 CLAUDE.md의 '콘텐츠 규칙'을 따른다. 웹과 MCP로 들어온 변경은 하단 '최근 변경 이력'에서 되돌릴 수 있다.
