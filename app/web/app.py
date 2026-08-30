"""FastAPI 应用组装：认证 + API 路由 + SPA 静态托管。

编辑端点依赖主进程持有的 client/conn/indexer；测试可传 None（只读断言）。
SPA dist 存在时挂到根路径；API 路由先注册，优先于静态兜底。
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.config import Config
from app.web.api import build_api_router
from app.web.auth import Sessions, build_auth_router

# web/dist：前端构建产物（W6 由 Docker multi-stage 产出；本地可 pnpm build）
_DIST = Path(__file__).resolve().parents[2] / "web" / "dist"


def create_app(
    config: Config,
    *,
    client=None,
    conn=None,
    indexer=None,
) -> FastAPI:
    sessions = Sessions()
    app = FastAPI(title="Telegram Archive Bot", version="0.2.0")
    app.state.sessions = sessions
    app.state.database_path = config.database_path
    app.state.client = client
    app.state.conn = conn
    app.state.indexer = indexer
    app.include_router(build_auth_router(config.web_token, sessions), prefix="/api/v1")
    app.include_router(build_api_router(config.database_path, config.config_path), prefix="/api/v1")
    if _DIST.is_dir():
        app.mount("/", StaticFiles(directory=_DIST, html=True), name="web")
    return app
