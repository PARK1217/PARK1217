from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from .. import services
from ..db import get_session
from ..schemas import LogIn, LogOut

router = APIRouter(prefix="/api/log", tags=["log"])
DB = Annotated[Session, Depends(get_session)]


@router.get("", response_model=list[LogOut])
def list_log(s: DB, days: int = Query(14, ge=1, le=366)):
    return services.list_log(s, days)


@router.post("", response_model=LogOut, status_code=status.HTTP_201_CREATED)
def add_log(body: LogIn, s: DB):
    return services.add_log(s, body.date, body.name, body.comp)


@router.delete("/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_log(entry_id: int, s: DB):
    services.delete_log(s, entry_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
