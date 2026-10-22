# 냉장고 사전 (fridge-dict)

집에서 쓰는 레시피·대체·보관·식단 기록 웹앱. 원래 claude.ai 아티팩트 한 장(`legacy/kitchen-index.html`)이었고, 이를 홈랩 서버로 옮긴다.
사용자는 두 명(부부). 주로 **주방에서 폰으로** 본다.

## 지켜야 할 것

- **디자인 정체성은 legacy 페이지를 따른다.** 폰트(Gowun Batang + IBM Plex Sans KR), 색 토큰, 다크 모드, 모바일 우선. 레이아웃과 구성 요소는 legacy보다 다듬어도 된다(2026-10-22 사용자 요청: "UI·UX와 레이아웃을 예쁘게"). 새 기능은 기존 톤에 맞춘다.
- 기능 목록 — 하나라도 빠지면 회귀다:
  - 탭: 레시피 / 대체·보관 / 식단
  - **분류(category) 선택** → 그 안에서 재료 칩 필터(여러 개 = AND), 검색(본문 텍스트 포함)
  - 모드: 전체 / 즐겨찾기 / 최근 추가 / 간단
  - 즐겨찾기(★) — 위로 정렬
  - 분량 배율 버튼(기준·1.5·2·3배), **기본값 1.5배**
  - 레시피별 주재료 입력칸 → 나머지 계량 비례 환산
  - 본문의 "N분/N초" 표기를 누르면 타이머 시작, 하단 바, 최대 3개 동시, 소리+진동
  - 오늘의 간단 요리 카드(날짜 기반, '다른 거')
  - 식단 탭: 단백질·채소·탄수화물·발효 4칸, 오늘 기록, 빠진 구성 추천, 지난 14일
  - 페이지 하단 "이 페이지를 늘려가는 규칙"
- 환산 제외: 온도, 시간, 크기(cm), `.key` 요령 상자 안의 숫자.

## 바뀌는 것 — 서버로 옮기는 이유

| 지금 (localStorage) | 서버 이후 |
|---|---|
| 즐겨찾기, 분량 배율, 식단 기록이 브라우저마다 따로 | **DB에 저장, 두 사람·여러 기기가 공유** |
| 레시피가 HTML 안의 JS 배열 | `data/recipes.json`, `data/swaps.json` → 첫 실행 때 DB로 시드 |
| 새 레시피 = HTML 통째로 다시 배포 | **데이터 파일만 추가하거나 API로 등록** |

타이머는 지금처럼 브라우저 로컬로 둔다(서버 저장 불필요).

## 스택

- 백엔드: **Python 3.12 + FastAPI + SQLite** (SQLAlchemy 2.0, `create_all`만 사용. Alembic 같은 마이그레이션 도구는 넣지 않는다).
- 프런트: `static/index.html` 한 파일. 데이터만 `fetch`로 받는다. **프레임워크(React 등) 도입하지 않는다.** 빌드 단계 없이 유지.
- 배포: Docker 단일 컨테이너 → Proxmox LXC, 외부 노출은 **Cloudflare Tunnel**, 접근 제한은 **Cloudflare Access(Zero Trust)** 이메일 인증. 앱 자체 로그인은 만들지 않는다.
- 도메인: 미정(`chobihome.com` 하위 서브도메인 예정). 하드코딩하지 말고 환경변수로.
- SQLite 파일은 볼륨으로 빼서 백업 가능하게.

## 디렉터리

```
app/            FastAPI. validation.py·services.py는 REST와 MCP가 공유한다
static/         index.html (프런트 한 파일)
legacy/         아티팩트 원본. 비교 기준이며 수정하지 않는다 (/legacy/ 경로로 같이 서빙)
data/           recipes.json, swaps.json — scripts/extract_legacy.mjs가 legacy에서 생성
scripts/        추출 스크립트
tests/          pytest
deploy/         배포 설정과 순서 (앱이 로컬에서 다 돌아간 뒤)
```

## 데이터 스키마

레시피 한 건 (`data/recipes.json`):

```json
{
  "id": "spam-kimchi-jjigae",
  "name": "스팸 김치찌개 (참치 없이)",
  "category": "가공식품",
  "tags": ["돼지고기", "김치"],
  "comp": ["단백질", "발효", "채소"],
  "tools": ["냄비"],
  "time": "45분",
  "easy": false,
  "base": "2인분",
  "anchor": { "n": "캔 스팸", "a": 200, "u": "g" },
  "added": "2026-10-14",
  "gist": "성패를 가르는 한 가지를 한 줄로.",
  "html": "<h3>...</h3><ol><li>...</li></ol><div class=\"key\">...</div><div class=\"swap\">...</div>"
}
```

- `id`: 영문 kebab-case, 고유. legacy에는 없으니 이관 때 생성(`scripts/extract_legacy.mjs`의 MAP).
- `category`: 한 건에 하나. 허용값은 `app/validation.py`의 `CATEGORY_ORDER`.
  - 레시피: `고기 · 해산물 · 두부·달걀 · 감자·채소 · 면·떡 · 가공식품`
  - 대체·보관: `재료 대체 · 손질·보관 · 도구·요령`
- `tags`: 주재료만, 최대 2개. 허용값은 `TAG_ORDER`(legacy와 동일).
- `comp`: `단백질·채소·탄수화물·발효` 중에서, **그 요리가 한 끼에서 실제로 맡는 역할만.** 고명은 세지 않는다. 양념 전용 항목은 빈 배열.
- `easy`: 아래 '간단' 기준을 만족할 때만 true.
- `anchor`: 사람들이 "이만큼 사왔는데"로 시작하는 재료. 단위는 `g·ml·개·장`. 없을 수 있다(쥐포 굽기, 홍게 활용).
- `html` 본문의 계량은 **반드시 `숫자+단위`** (`2큰술`, `150ml`, `½작은술`). `고추장 2 · 간장 1` 처럼 단위를 빼면 환산이 안 된다. `전분 1 : 물 2큰술` 같은 비율 표기는 허용.
- 대체·보관 항목(`data/swaps.json`)은 같은 형태에서 `comp/easy/base/anchor` 없음.

## 콘텐츠 규칙 (legacy 하단 규칙과 동일 — 바꿀 때는 사용자에게 먼저 묻는다)

**넣는 것**
- 실제로 만들어 본 요리만. 목록만 받고 안 해본 건 넣지 않는다.
- 각 레시피에 `없을 때`(재료 빼기·바꾸기) 정보를 가능하면 함께.

**넣지 않는 것**
- 밀키트 요리 자체 → 레시피로 넣지 않고 '대체·보관 › 밀키트에 재료를 더할 때'에 요령만 보탠다.
- 한 번 쓰고 마는 상황별 조치.
- 칼로리·영양소 수치. 구성(4칸)만 표시한다.

**'간단'의 기준**
- 15분 안에 상에 올라가고, 핏물 빼기·불리기·오래 삶기 같은 기다리는 손질이 없을 것.
- 집에 상시 있는 재료로 될 것.
- 국물 요리는 20분까지 허용.
- 양념만 만드는 항목은 제외.

**분량**
- 두 사람 다 대식가라 일반 2인분은 기준으로 부족하다. 레시피 `base`는 원래 레시피 기준 그대로 적고, 화면 기본 배율을 1.5배로 둔다.

**늘어나면 이 순서로 고친다**
- (도입됨) 분류 › 재료 칩 2단계. 80개 기준이었지만 2026-10-22 사용자 요청으로 먼저 넣었다.
- 40개 넘으면: 기구 필터(큐커·에어프라이어·오븐·인덕션·전자레인지)
- 60개 넘으면: 시간 필터, 재료 칩 접기
- 그 전이라도 찾기 불편하면 먼저 고친다.

## 집 주방 기구 (레시피 쓸 때 참고)

- 인덕션 (일반 흙 뚝배기 불가)
- 삼성 큐커: **상단 히터가 강하고 왼쪽이 더 세다. 트레이는 최상단 한 칸만.** 얇은 건 반드시 중간에 뒤집기, 온도는 한 단계 낮게.
- 삼성 빌트인 오븐(컨벡션), 에어프라이어, 전자레인지
- 냄비 중 하나는 2L가 최대

## API

```
GET    /api/recipes            레시피 전체 (seq 순)
GET    /api/recipes/{id}
POST   /api/recipes            추가 (JSON 스키마 검증) → 201
PUT    /api/recipes/{id}       수정 (부분 patch, 병합 후 전체 검증)
GET    /api/swaps              대체·보관 전체
GET    /api/swaps/{id}
POST   /api/swaps
PUT    /api/swaps/{id}
GET    /api/state              { favs: [id...], scale }
PUT    /api/state              { favs?, scale? }
GET    /api/log?days=14        식단 기록 (오늘 포함 최근 N일)
POST   /api/log                {date, name, comp[]} → 201
DELETE /api/log/{entry_id}     → 204
GET    /api/history?kind=&id=  변경 이력 (되돌리기 UI는 2단계)
```

- `POST/PUT` 시 검증 실패는 400 + `{"detail": "...", "errors": ["문장", ...]}`. 계량 표기 검사: 본문에 단위 없는 숫자 나열이 있으면 어느 항목이 왜 틀렸는지 문장으로 돌려준다.
- 사용자 구분은 Cloudflare Access가 넣는 `Cf-Access-Authenticated-User-Email` 헤더로. 로컬에서는 `DEV_USER_EMAIL`(기본 `local@dev`). 즐겨찾기는 **사람별**, 식단 기록과 분량 배율은 **가구 공용**.
- 모든 추가·수정은 `history` 테이블에 이전 버전과 `source`(web/mcp/seed)를 남긴다.

## 결정 기록 (2026-10-22)

- 태그 2개 제한은 POST/PUT에서만 강제. 시드는 legacy 원문 그대로 넣고 경고만 남긴다(삼겹살 카레·부대찌개가 3개).
- 첫 접속 때 브라우저 localStorage의 즐겨찾기·배율·식단 기록이 있고 서버가 비어 있으면 한 번 올리고 로컬 키를 지운다. 즐겨찾기는 이름→id로 변환.
- 푸터의 "새 대화에서 추가할 때" 문단은 아티팩트 시절 안내라 틀리지만, MCP가 붙는 2단계에서 함께 고친다.
- 저장소: `PARK1217/fridge-dict`를 만들 권한이 세션에 없어, 생성 전까지 `PARK1217/PARK1217`의 작업 브랜치 `fridge-dict/` 하위 폴더에서 개발한다. 새 저장소가 생기면 폴더 이력을 옮긴다.

## 2단계: MCP 엔드포인트 (앱과 배포가 끝난 뒤)

목적: claude.ai 대화에서 Claude가 레시피를 직접 넣고 고칠 수 있게 한다. 앱을 claude.ai **커스텀 커넥터**로 등록해서, 대화 중 "사전에 넣어줘"가 곧 DB 반영이 되게.

- 같은 FastAPI 앱에 `/mcp` 경로로 붙인다. 공식 Python MCP SDK, **Streamable HTTP** 전송.
- 도구는 REST와 **같은 검증 로직을 공유**한다(`app/validation.py`, `app/services.py`). 따로 구현하지 않는다.
- 도구 목록:
  - `list_recipes(query?, tag?)` / `get_recipe(id)` — 추가 전에 중복 확인용. 목록은 id·name·tags·gist만.
  - `add_recipe(recipe)` / `update_recipe(id, patch)`
  - `list_swaps()` / `get_swap(id)` / `add_swap(swap)` / `update_swap(id, patch)`
  - `log_meal(date, name, comp[])`
  - 삭제 도구는 만들지 않는다. 삭제는 웹 화면에서 사람이 한다.
- 도구 description(한국어)에 CLAUDE.md의 **콘텐츠 규칙 요약**을 넣는다 — 실제로 해본 것만, 밀키트는 swap에, comp 기준, '간단' 기준, 계량은 숫자+단위. 어느 대화의 Claude든 이 설명만 보고 규칙대로 넣을 수 있어야 한다.
- 검증 실패 시 무엇이 왜 틀렸는지 문장으로 돌려준다(Claude가 고쳐서 재시도할 수 있게).
- **변경 이력**: add/update마다 이전 버전을 `history` 테이블에 남기고, 웹 화면에서 되돌리기 가능하게. `source`(web/mcp) 기록.
- **인증**: `/mcp`만 Cloudflare Access 정책에서 bypass하고, 대신 claude.ai 커스텀 커넥터가 지원하는 방식(OAuth 등)으로 보호한다. **구현 전에 claude.ai 커스텀 커넥터의 현재 인증 요건을 문서로 확인**하고, 방법을 정리해 승인받은 뒤 진행. `/mcp`를 인증 없이 열어두는 건 금지.
- 완료 기준: claude.ai에서 커넥터를 연결한 대화가 `list_recipes`로 목록을 읽고, 테스트 레시피를 `add_recipe`로 넣고, 웹 화면에 바로 보이고, 이력에서 되돌릴 수 있을 것.

## 작업 방식

- 큰 변경 전에 계획을 먼저 보여주고 승인받는다.
- legacy 페이지와 나란히 띄워 기능이 빠지지 않았는지, 톤이 같은지 확인한 뒤 완료라고 한다. 폰 너비(390px)에서도 확인.
- 이관 후 legacy의 레시피 수(24)와 대체·보관 수(21)가 DB와 일치하는지 테스트로 확인.
- 응답과 커밋 메시지는 한국어.

## 로컬 실행

```
pip install -r requirements.txt -r requirements-dev.txt
uvicorn app.main:app --reload --port 8080     # 첫 실행 때 data/*.json을 자동 시드
pytest -q
node scripts/extract_legacy.mjs --check       # data/*.json이 legacy와 일치하는지
```
