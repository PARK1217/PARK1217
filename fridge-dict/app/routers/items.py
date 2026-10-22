"""레시피와 대체·보관은 같은 모양이라 라우터 하나를 kind별로 두 번 만든다."""
from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from .. import services
from ..auth import CurrentUser
from ..db import get_session
from ..schemas import RecipeIn, RecipePatch, SwapIn, SwapPatch

DB = Annotated[Session, Depends(get_session)]


def make_router(kind: str) -> APIRouter:
    plural = "recipes" if kind == "recipe" else "swaps"
    In = RecipeIn if kind == "recipe" else SwapIn
    Patch = RecipePatch if kind == "recipe" else SwapPatch
    r = APIRouter(prefix=f"/api/{plural}", tags=[plural])

    @r.get("")
    def list_all(s: DB):
        return services.list_items(s, kind)

    @r.get("/{item_id}")
    def get_one(item_id: str, s: DB):
        return services.get_item(s, kind, item_id)

    @r.post("", status_code=status.HTTP_201_CREATED)
    def create(body: In, s: DB, user: CurrentUser):  # type: ignore[valid-type]
        return services.create_item(s, kind, body.model_dump(), source="web", user=user)

    @r.put("/{item_id}")
    def update(item_id: str, body: Patch, s: DB, user: CurrentUser):  # type: ignore[valid-type]
        patch = body.model_dump(exclude_unset=True)
        return services.update_item(s, kind, item_id, patch, source="web", user=user)

    return r


recipes = make_router("recipe")
swaps = make_router("swap")

history = APIRouter(prefix="/api/history", tags=["history"])


@history.get("")
def list_history(s: DB, kind: str | None = None, id: str | None = None, limit: int = 50):
    return services.list_history(s, kind, id, min(max(limit, 1), 200))


_ = Response  # noqa: F841 (명시적 import 유지)
