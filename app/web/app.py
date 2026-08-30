"""FastAPI 应用组装：认证 + API 路由，会话存入 app.state 供依赖使用。"""

from __future__ import annotations

from fastapi import FastAPI

from app.config import Config
from app.web.api import build_api_router
from app.web.auth import Sessions, build_auth_router


def create_app(config: Config) -> FastAPI:
    sessions = Sessions()
    app = FastAPI(title="Telegram Archive Bot", version="0.2.0")
    app.state.sessions = sessions
    app.state.database_path = config.database_path
    app.include_router(build_auth_router(config.web_token, sessions), prefix="/api/v1")
    app.include_router(build_api_router(config.database_path), prefix="/api/v1")
    return app
