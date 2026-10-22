"""사용자 구분. Cloudflare Access가 넣는 헤더를 읽고, 없으면 로컬 개발용 기본값."""
from typing import Annotated

from fastapi import Depends, Request

from .config import DEV_USER_EMAIL, USER_HEADER


def get_user_email(request: Request) -> str:
    v = request.headers.get(USER_HEADER)
    return v.strip().lower() if v and v.strip() else DEV_USER_EMAIL


CurrentUser = Annotated[str, Depends(get_user_email)]
