"""냉장고 사전 — FastAPI 앱. 시작 때 테이블을 만들고 data/*.json을 시드한다."""
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .config import LEGACY_DIR, STATIC_DIR
from .db import SessionLocal, init_db
from .routers import items, log, state
from .seed import seed
from .services import Conflict, NotFound
from .validation import ANCHOR_UNITS, CATEGORY_ORDER, COMPS, TAG_ORDER, ValidationError


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    with SessionLocal() as s:
        seed(s)
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
    return {"tags": TAG_ORDER, "categories": CATEGORY_ORDER, "comps": COMPS, "anchor_units": list(ANCHOR_UNITS)}


# legacy 원본을 /legacy/ 에 같이 띄워 나란히 비교할 수 있게 한다.
if LEGACY_DIR.exists():
    @app.get("/legacy/", include_in_schema=False)
    def legacy_page():
        return FileResponse(LEGACY_DIR / "kitchen-index.html")

# 정적 파일은 맨 마지막에 마운트 (앞의 /api 경로를 가리지 않게)
app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
