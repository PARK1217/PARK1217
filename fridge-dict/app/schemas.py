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


class StatePut(BaseModel):
    model_config = ConfigDict(extra="forbid")
    favs: list[str] | None = None
    scale: float | None = Field(default=None, gt=0, le=10)


class LogIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    date: str
    name: str
    comp: list[str] = Field(default_factory=list)


class LogOut(BaseModel):
    id: int
    date: str
    name: str
    comp: list[str]


class HistoryOut(BaseModel):
    id: int
    kind: str
    item_id: str
    action: str
    data: dict
    source: str
    user_email: str
    changed_at: str
