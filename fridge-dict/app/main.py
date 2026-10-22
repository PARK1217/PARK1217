"""냉장고 사전 — FastAPI 앱. 시작 때 테이블을 만들고 data/*.json을 시드한다."""
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .config import LEGACY_DIR, MCP_ENABLED, MCP_SECRET, STATIC_DIR
from .db import SessionLocal, init_db
from .routers import items, log, state
from .seed import seed
from .services import Conflict, NotFound
from .validation import ANCHOR_UNITS, CATEGORY_ORDER, COMPS, TAG_ORDER, ValidationError


# MCP(claude.ai 커스텀 커넥터): MCP_SECRET이 있을 때만 /mcp/<secret> 에 붙는다.
_mcp = None
_mcp_http = None
if MCP_ENABLED:
    from .mcp_server import build_http_app

    _mcp, _mcp_http = build_http_app(f"/{MCP_SECRET}")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    with SessionLocal() as s:
        seed(s)
    if _mcp is not None:
        # 마운트된 서브앱의 lifespan은 돌지 않으므로 세션 매니저를 여기서 연다
        async with _mcp.session_manager.run():
            print("[mcp] 켜짐: /mcp/<secret> (경로는 로그에 남기지 않음)")
            yield
    else:
        print("[mcp] 꺼짐: MCP_SECRET이 없거나 32자 미만")
        yield


app = FastAPI(title="냉장고 사전", lifespan=lifespan, docs_url="/api/docs", redoc_url=None, openapi_url="/api/openapi.json")


@app.exception_handler(ValidationError)
async def _validation(_: Request, exc: ValidationError):
    return JSONResponse(status_code=400, content={"detail": "검증 실패: " + exc.errors[0], "errors": exc.errors})


@app.exception_handler(NotFound)
async def _not_found(_: Request, exc: NotFound):
    return JSONResponse(status_code=404, content={"detail": str(exc)})


@app.exception_handler(Conflict)
async def _conflict(_: Request, exc: Conflict):
    return JSONResponse(status_code=409, content={"detail": str(exc)})


app.include_router(items.recipes)
app.include_router(items.swaps)
app.include_router(items.history)
app.include_router(state.router)
app.include_router(log.router)


@app.get("/api/health")
def health():
    return {"ok": True}


@app.get("/api/meta")
def meta():
    """프런트가 칩·분류 순서를 하드코딩하지 않도록 허용값을 내려준다 (validation.py가 단일 출처)."""
    return {"tags": TAG_ORDER, "categories": CATEGORY_ORDER, "comps": COMPS, "anchor_units": list(ANCHOR_UNITS), "mcp": MCP_ENABLED}


if _mcp_http is not None:
    app.mount("/mcp", _mcp_http, name="mcp")


# legacy 원본을 /legacy/ 에 같이 띄워 나란히 비교할 수 있게 한다.
if LEGACY_DIR.exists():
    @app.get("/legacy/", include_in_schema=False)
    def legacy_page():
        return FileResponse(LEGACY_DIR / "kitchen-index.html")

# 정적 파일은 맨 마지막에 마운트 (앞의 /api 경로를 가리지 않게)
app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
