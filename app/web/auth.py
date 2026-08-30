"""Web 会话鉴权：登录换内存会话，cookie HttpOnly；重启后清空需重新登录。

登录端点比对 WEB_TOKEN（恒时比较），通过后签发随机会话 id 存内存，
客户端带 HttpOnly + SameSite=Lax cookie。多人复用、会话撤销等超出个人工具
场景，不做持久会话表。
"""

from __future__ import annotations

import secrets
import time

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel

COOKIE_NAME = "archive_session"
_SESSION_TTL = 7 * 24 * 3600


class Sessions:
    """内存会话表：id -> 过期时间戳。"""

    def __init__(self) -> None:
        self._tokens: dict[str, float] = {}

    def create(self) -> str:
        sid = secrets.token_urlsafe(32)
        self._tokens[sid] = time.time() + _SESSION_TTL
        return sid

    def valid(self, sid: str | None) -> bool:
        if not sid:
            return False
        exp = self._tokens.get(sid)
        if not exp:
            return False
        if time.time() > exp:
            self._tokens.pop(sid, None)
            return False
        return True

    def drop(self, sid: str | None) -> None:
        if sid:
            self._tokens.pop(sid, None)


class LoginBody(BaseModel):
    token: str


def build_auth_router(web_token: str, sessions: Sessions) -> APIRouter:
    router = APIRouter()

    @router.post("/auth/login")
    def login(body: LoginBody, response: Response):
        if not secrets.compare_digest(body.token, web_token):
            raise HTTPException(status_code=401, detail="invalid token")
        sid = sessions.create()
        response.set_cookie(
            COOKIE_NAME,
            sid,
            httponly=True,
            samesite="lax",
            max_age=_SESSION_TTL,
        )
        return {"ok": True}

    @router.post("/auth/logout")
    def logout(request: Request, response: Response):
        sessions.drop(request.cookies.get(COOKIE_NAME))
        response.delete_cookie(COOKIE_NAME)
        return {"ok": True}

    return router
