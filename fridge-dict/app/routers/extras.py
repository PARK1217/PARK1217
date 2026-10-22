"""해볼 것 · 메모 · 주간 계획 · 내보내기."""
import datetime as dt
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from .. import services
from ..auth import CurrentUser
from ..db import get_session
from ..schemas import IdeaIn, IdeaOut, IdeaPatch, NoteIn, NoteOut, PlanIn, PlanOut

DB = Annotated[Session, Depends(get_session)]

ideas = APIRouter(prefix="/api/ideas", tags=["ideas"])
notes = APIRouter(prefix="/api/notes", tags=["notes"])
plan = APIRouter(prefix="/api/plan", tags=["plan"])
export = APIRouter(prefix="/api/export", tags=["export"])


@ideas.get("", response_model=list[IdeaOut])
def list_ideas(s: DB, include_done: bool = True):
    return services.list_ideas(s, include_done)


@ideas.post("", response_model=IdeaOut, status_code=status.HTTP_201_CREATED)
def add_idea(body: IdeaIn, s: DB):
    return services.add_idea(s, body.name, body.note, body.kind, source="web")


@ideas.put("/{idea_id}", response_model=IdeaOut)
def update_idea(idea_id: int, body: IdeaPatch, s: DB):
    return services.update_idea(s, idea_id, body.model_dump(exclude_unset=True))


@ideas.delete("/{idea_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_idea(idea_id: int, s: DB):
    services.delete_idea(s, idea_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@notes.get("", response_model=list[NoteOut])
def list_notes(s: DB, kind: str, id: str):
    return services.list_notes(s, kind, id)


@notes.post("", response_model=NoteOut, status_code=status.HTTP_201_CREATED)
def add_note(body: NoteIn, s: DB, user: CurrentUser):
    return services.add_note(s, body.kind, body.item_id, body.text, user=user)


@notes.delete("/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_note(note_id: int, s: DB):
    services.delete_note(s, note_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@plan.get("", response_model=list[PlanOut])
def list_plan(s: DB, start: str = Query(None), end: str = Query(None)):
    """기본은 이번 주 월요일부터 2주."""
    if not start:
        today = dt.date.today()
        start = (today - dt.timedelta(days=today.weekday())).isoformat()
    if not end:
        end = (dt.date.fromisoformat(start) + dt.timedelta(days=13)).isoformat()
    return services.list_plan(s, start, end)


@plan.post("", response_model=PlanOut, status_code=status.HTTP_201_CREATED)
def add_plan(body: PlanIn, s: DB):
    return services.add_plan(s, body.date, body.name, body.recipe_id)


@plan.delete("/{plan_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_plan(plan_id: int, s: DB):
    services.delete_plan(s, plan_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@export.get("")
def export_all(s: DB):
    """레시피·대체·식단·해볼 것·메모·계획·설정을 JSON 하나로. 백업용."""
    return services.export_all(s)
