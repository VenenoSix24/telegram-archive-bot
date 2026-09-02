"""路由共享件：鉴权依赖与路由上下文。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from fastapi import HTTPException, Request

from app.web.auth import COOKIE_NAME


def require_auth(request: Request) -> None:
    sid = request.cookies.get(COOKIE_NAME)
    sessions = request.app.state.sessions
    if not sessions.valid(sid):
        raise HTTPException(status_code=401, detail="unauthorized")


@dataclass
class WebContext:
    """路由层共享上下文：数据库/配置路径与运行时对象（client、会话名）。"""

    database_path: str
    config: Any = None
    config_path: str | None = None
    client: Any = None
    chat_names: dict[int, str] | None = None

    @property
    def target_names(self) -> dict[int, str]:
        """目标 chat_id → 人读名：配置备注名打底，运行时会话名覆盖。"""
        names = {
            target.chat_id: target.name
            for target in getattr(self.config, "target_channels", [])
            if target.name
        }
        names.update(self.chat_names or {})
        return names
