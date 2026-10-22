"""claude.ai 커스텀 커넥터용 MCP 서버.

도구는 REST와 같은 services·validation을 쓴다. 따로 검증을 구현하지 않는다.
검증 실패는 ToolError로 돌려주어 Claude가 문장을 읽고 고쳐서 다시 시도할 수 있게 한다.
"""
from __future__ import annotations

import datetime as dt

from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.server.transport_security import TransportSecuritySettings

from . import services
from .config import APP_DOMAIN
from .db import SessionLocal
from .schemas import RecipeIn, RecipePatch, SwapIn, SwapPatch
from .validation import CATEGORY_ORDER, COMPS, SPICY, TAG_ORDER, ValidationError

MCP_USER = "claude.ai"  # 로그인 없는 비밀 URL 방식이라 사람은 구분하지 않는다. 이력에는 source=mcp로 남는다.

RULES = f"""냉장고 사전 — 부부 두 사람이 주방에서 폰으로 보는 레시피·대체·보관 사전입니다.

## 넣을 때 지키는 규칙
- 실제로 만들어 본 요리만 넣습니다. 목록만 받고 안 해본 것, 아이디어 단계는 넣지 않습니다.
- 밀키트 요리 자체는 레시피로 넣지 않습니다. 재료를 더할 때의 요령만 대체·보관의 '밀키트에 재료를 더할 때'(id: mealkit-additions)에 update_swap으로 보탭니다.
- 한 번 쓰고 마는 상황별 조치, 칼로리·영양소 수치는 넣지 않습니다.
- 추가 전에 반드시 list_recipes / list_swaps 로 같은 요리가 이미 있는지 확인하고, 있으면 update_* 로 고칩니다.

## 필드
- id: 영문 소문자 kebab-case, 고유 (예: spam-kimchi-jjigae)
- name: 이름. gist: 그 요리의 성패를 가르는 한 가지를 한 줄로 (설명이 아니라 판단 기준)
- category(레시피): {' · '.join(CATEGORY_ORDER['recipe'])} 중 하나
- category(대체·보관): {' · '.join(CATEGORY_ORDER['swap'])} 중 하나
- tags: 주재료만 최대 2개. 레시피 허용값: {' · '.join(TAG_ORDER['recipe'])} / 대체·보관 허용값: {' · '.join(TAG_ORDER['swap'])}
- comp: {' · '.join(COMPS)} 중에서 그 요리가 한 끼에서 실제로 맡는 역할만. 고명은 세지 않고, 양념 전용 항목은 빈 배열.
- easy: 15분 안에 상에 올라가고 핏물 빼기·불리기·오래 삶기 같은 기다리는 손질이 없고, 집에 상시 있는 재료로 될 때만 true. 국물 요리는 20분까지 허용. 양념만 만드는 항목은 false.
- base: 원래 레시피 기준 분량 그대로 (예: "2인분"). 화면이 1.5배로 환산해 보여주므로 늘려 적지 않습니다.
- spicy: {' · '.join(SPICY)} 중 하나, 모르면 비움. 한 사람이 매운 걸 덜 먹어서 '덜 맵게' 필터에 쓴다.
- anchor: 사람들이 "이만큼 사왔는데"로 시작하는 주재료. {{"n": "캔 스팸", "a": 200, "u": "g"}} 형태, u는 g·ml·개·장. 없으면 생략.
- tools: 기구 목록 (냄비·팬·큐커·에어프라이어·오븐·전자레인지·뚝배기·찜기·무조리 등). time: "45분"처럼 표시용 문자열. added: YYYY-MM-DD.
- html: 본문. <h3>·<ol>/<ul>·<b>·<p> 와 요령 상자 <div class="key">, 없을 때 상자 <div class="swap"><h3>없을 때</h3><ul>…</ul></div> 만 씁니다.

## 계량 표기 (가장 자주 틀리는 것)
본문의 계량은 반드시 '숫자+단위'로 붙여 씁니다: 2큰술, 150ml, ½작은술, 달걀 3개, 두부 ½모.
'고추장 2 · 간장 1' 처럼 단위를 빼면 거절됩니다. 비율은 '전분 1 : 물 2큰술' 처럼 ':'로 적습니다.
시간(3분)·온도(200도)·크기(1cm)는 단위가 있으니 그대로 됩니다. 환산 대상에서 빼고 싶은 숫자는 <div class="key"> 안에 둡니다.

## 집 주방 기구 (레시피 쓸 때 참고)
인덕션(흙 뚝배기 불가), 삼성 큐커(상단 히터가 강하고 왼쪽이 더 셈, 트레이는 최상단 한 칸, 얇은 건 중간에 뒤집고 온도는 한 단계 낮게), 빌트인 컨벡션 오븐, 에어프라이어, 전자레인지. 냄비는 2L가 최대.

## 아직 안 해본 것
해보지 않은 아이디어는 add_recipe가 아니라 add_idea(해볼 것)에 넣습니다. 해본 뒤 레시피로 옮깁니다.

삭제 도구는 없습니다. 삭제와 되돌리기는 웹 화면에서 사람이 합니다. 모든 추가·수정은 이력에 남습니다."""


def _fail(e: Exception) -> ToolError:
    if isinstance(e, ValidationError):
        return ToolError("검증 실패. 아래를 고쳐서 다시 보내세요.\n- " + "\n- ".join(e.errors))
    return ToolError(str(e))


def _transport_security() -> TransportSecuritySettings:
    if APP_DOMAIN:
        return TransportSecuritySettings(
            enable_dns_rebinding_protection=True,
            allowed_hosts=[APP_DOMAIN, f"{APP_DOMAIN}:*", "127.0.0.1:*", "localhost:*"],
            allowed_origins=[f"https://{APP_DOMAIN}", "http://127.0.0.1:*", "http://localhost:*"],
        )
    return TransportSecuritySettings(enable_dns_rebinding_protection=False)


def build_server() -> MCPServer:
    mcp = MCPServer("냉장고 사전", instructions=RULES)

    # ── 레시피 ──────────────────────────────────────────────────────────
    @mcp.tool(description="레시피 목록. 추가 전에 같은 요리가 있는지 여기서 먼저 확인합니다. query는 이름·요약·본문 부분 일치, tag는 주재료 태그. id·name·category·tags·gist만 돌려줍니다.")
    def list_recipes(query: str = "", tag: str = "") -> list[dict]:
        with SessionLocal() as s:
            return services.search_items(s, "recipe", query, tag)

    @mcp.tool(description="레시피 한 건의 전체 내용(html 본문 포함). 수정 전에 현재 본문을 읽을 때 씁니다.")
    def get_recipe(id: str) -> dict:
        with SessionLocal() as s:
            try:
                return services.get_item(s, "recipe", id)
            except services.NotFound as e:
                raise _fail(e)

    @mcp.tool(description="레시피 추가. 실제로 만들어 본 요리만. 규칙은 서버 안내(instructions)를 따르고, 계량은 반드시 '숫자+단위'(2큰술, 150ml). 검증에 걸리면 무엇이 왜 틀렸는지 문장으로 돌려주니 고쳐서 다시 보내세요.")
    def add_recipe(recipe: RecipeIn) -> dict:
        with SessionLocal() as s:
            try:
                d = services.create_item(s, "recipe", recipe.model_dump(), source="mcp", user=MCP_USER)
            except (ValidationError, services.Conflict) as e:
                raise _fail(e)
            return {"ok": True, "id": d["id"], "name": d["name"], "message": "추가했습니다. 웹 화면에 바로 보입니다."}

    @mcp.tool(description="레시피 수정. 바꿀 필드만 patch에 넣습니다(부분 수정). 합친 결과를 전체 검증하므로 html을 고칠 때도 계량 '숫자+단위' 규칙이 적용됩니다. 수정 전 버전은 이력에 남아 웹에서 되돌릴 수 있습니다.")
    def update_recipe(id: str, patch: RecipePatch) -> dict:
        with SessionLocal() as s:
            try:
                d = services.update_item(s, "recipe", id, patch.model_dump(exclude_unset=True), source="mcp", user=MCP_USER)
            except (ValidationError, services.NotFound) as e:
                raise _fail(e)
            return {"ok": True, "id": d["id"], "name": d["name"], "message": "수정했습니다."}

    # ── 대체·보관 ───────────────────────────────────────────────────────
    @mcp.tool(description="대체·보관 항목 목록(재료 대체, 손질·보관, 도구·요령). 밀키트 요령은 'mealkit-additions'에 모읍니다. query 부분 일치. id·name·category·tags·gist만 돌려줍니다.")
    def list_swaps(query: str = "", tag: str = "") -> list[dict]:
        with SessionLocal() as s:
            return services.search_items(s, "swap", query, tag)

    @mcp.tool(description="대체·보관 항목 한 건의 전체 내용(html 본문 포함).")
    def get_swap(id: str) -> dict:
        with SessionLocal() as s:
            try:
                return services.get_item(s, "swap", id)
            except services.NotFound as e:
                raise _fail(e)

    @mcp.tool(description="대체·보관 항목 추가. 같은 일이 또 생길 만한 것만. category는 재료 대체·손질·보관·도구·요령 중 하나, tags는 최대 2개. 계량은 '숫자+단위'.")
    def add_swap(swap: SwapIn) -> dict:
        with SessionLocal() as s:
            try:
                d = services.create_item(s, "swap", swap.model_dump(), source="mcp", user=MCP_USER)
            except (ValidationError, services.Conflict) as e:
                raise _fail(e)
            return {"ok": True, "id": d["id"], "name": d["name"], "message": "추가했습니다."}

    @mcp.tool(description="대체·보관 항목 수정. 바꿀 필드만 patch에. 밀키트에 요령을 보탤 때는 get_swap('mealkit-additions')로 본문을 읽고 <ul>에 항목을 더한 html을 보냅니다.")
    def update_swap(id: str, patch: SwapPatch) -> dict:
        with SessionLocal() as s:
            try:
                d = services.update_item(s, "swap", id, patch.model_dump(exclude_unset=True), source="mcp", user=MCP_USER)
            except (ValidationError, services.NotFound) as e:
                raise _fail(e)
            return {"ok": True, "id": d["id"], "name": d["name"], "message": "수정했습니다."}

    # ── 식단 기록 ───────────────────────────────────────────────────────
    @mcp.tool(description="식단 기록 추가(가구 공용). date는 YYYY-MM-DD, 비우면 오늘. comp는 단백질·채소·탄수화물·발효 중 그 끼니가 실제로 맡은 것만. 사전에 있는 요리면 그 레시피의 comp를 그대로 씁니다.")
    def log_meal(name: str, comp: list[str] | None = None, date: str = "") -> dict:
        with SessionLocal() as s:
            try:
                e = services.add_log(s, date or dt.date.today().isoformat(), name, comp or [])
            except ValidationError as ex:
                raise _fail(ex)
            return {"ok": True, "entry": e}

    # ── 해볼 것 ─────────────────────────────────────────────────────────
    @mcp.tool(description="해볼 것 목록(아직 안 해본 아이디어). 레시피로 넣기 전 단계. 완료된 것도 뒤에 붙어 옵니다.")
    def list_ideas() -> list[dict]:
        with SessionLocal() as s:
            return services.list_ideas(s)

    @mcp.tool(description="해볼 것 추가. 실제로 안 해본 요리·요령은 add_recipe 대신 여기에. name은 요리 이름, note는 왜 끌리는지·출처·핵심 요령 한두 줄. kind는 recipe(기본) 또는 swap.")
    def add_idea(name: str, note: str = "", kind: str = "recipe") -> dict:
        with SessionLocal() as s:
            try:
                d = services.add_idea(s, name, note, kind, source="mcp")
            except ValidationError as e:
                raise _fail(e)
            return {"ok": True, "idea": d, "message": "해볼 것에 넣었습니다. 해본 뒤 웹에서 '레시피로 옮기기'를 누르거나 add_recipe로 넣으세요."}

    return mcp


def build_http_app(secret_path: str):
    """FastAPI에 /mcp 아래로 마운트할 Starlette 앱. 엔드포인트는 /mcp{secret_path}.
    무상태 + JSON 응답: 세션 친화성이 필요 없어 Cloudflare 뒤에서도 단순하게 동작한다."""
    mcp = build_server()
    app = mcp.streamable_http_app(
        streamable_http_path=secret_path,
        stateless_http=True,
        json_response=True,
        transport_security=_transport_security(),
    )
    return mcp, app
