"""API 입출력 형태. 도메인 규칙(허용 태그·계량 표기 등)은 validation.py가 맡는다."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class Anchor(BaseModel):
    n: str
    a: float
    u: str


class RecipeIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    name: str
    category: str
    tags: list[str]
    comp: list[str] = Field(default_factory=list)
    tools: list[str] = Field(default_factory=list)
    time: str = ""
    easy: bool = False
    base: str = ""
    anchor: Anchor | None = None
    spicy: str = ""
    added: str
    gist: str
    html: str


class RecipePatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = None
    category: str | None = None
    tags: list[str] | None = None
    comp: list[str] | None = None
    tools: list[str] | None = None
    time: str | None = None
    easy: bool | None = None
    base: str | None = None
    anchor: Anchor | None = None
    spicy: str | None = None
    added: str | None = None
    gist: str | None = None
    html: str | None = None


class SwapIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    name: str
    category: str
    tags: list[str]
    tools: list[str] = Field(default_factory=list)
    time: str = ""
    added: str
    gist: str
    html: str


class SwapPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = None
    category: str | None = None
    tags: list[str] | None = None
    tools: list[str] | None = None
    time: str | None = None
    added: str | None = None
    gist: str | None = None
    html: str | None = None


class StateOut(BaseModel):
    favs: list[str]
    scale: float
    stock: list[str]


class StatePut(BaseModel):
    model_config = ConfigDict(extra="forbid")
    favs: list[str] | None = None
    scale: float | None = Field(default=None, gt=0, le=10)
    stock: list[str] | None = None


class LogIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    date: str
    name: str
    comp: list[str] = Field(default_factory=list)
    recipe_id: str | None = None


class LogOut(BaseModel):
    id: int
    date: str
    name: str
    comp: list[str]
    recipe_id: str | None = None


class IdeaIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    note: str = ""
    kind: str = "recipe"


class IdeaPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = None
    note: str | None = None
    kind: str | None = None
    done: bool | None = None


class IdeaOut(BaseModel):
    id: int
    kind: str
    name: str
    note: str
    source: str
    created_at: str
    done_at: str | None


class NoteIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: str
    item_id: str
    text: str


class NoteOut(BaseModel):
    id: int
    kind: str
    item_id: str
    text: str
    user_email: str
    created_at: str


class PlanIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    date: str
    name: str
    recipe_id: str | None = None


class PlanOut(BaseModel):
    id: int
    date: str
    name: str
    recipe_id: str | None


class HistoryOut(BaseModel):
    id: int
    kind: str
    item_id: str
    action: str
    data: dict
    source: str
    user_email: str
    changed_at: str
