from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import services
from ..auth import CurrentUser
from ..db import get_session
from ..schemas import StateOut, StatePut

router = APIRouter(prefix="/api/state", tags=["state"])
DB = Annotated[Session, Depends(get_session)]


@router.get("", response_model=StateOut)
def get_state(s: DB, user: CurrentUser):
    return services.get_state(s, user)


@router.put("", response_model=StateOut)
def put_state(body: StatePut, s: DB, user: CurrentUser):
    return services.put_state(s, user, favs=body.favs, scale=body.scale)
