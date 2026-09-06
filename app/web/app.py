"""FastAPI 应用组装：认证 + API 路由 + SPA 静态托管。

编辑端点依赖主进程持有的 client/conn/indexer；测试可传 None（只读断言）。
SPA dist 存在时挂到根路径；API 路由先注册，优先于静态兜底。
"""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.config import Config
from app.task_failures import last_failure
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
    chat_names: dict[int, str] | None = None,
    queue=None,
    auto_backup=None,
) -> FastAPI:
    sessions = Sessions()
    app = FastAPI(title="Telegram Archive Bot", version="0.2.0")
    app.state.sessions = sessions
    app.state.database_path = config.database_path
    app.state.client = client
    app.state.conn = conn
    app.state.indexer = indexer
    app.state.queue = queue
    app.state.auto_backup = auto_backup
    app.state.started_at = time.monotonic()

    @app.get("/health")
    def health() -> dict:
        """负载均衡探活端点：不经过鉴权，只暴露非敏感信息（无路径/配置值）。"""
        payload: dict = {
            "status": "ok",
            "database": {"reachable": False, "user_version": None},
            "last_failure": None,
            "uptime_seconds": round(time.monotonic() - app.state.started_at, 3),
            "version": app.version,
        }
        try:
            conn = sqlite3.connect(config.database_path)
            try:
                user_version = conn.execute("PRAGMA user_version").fetchone()[0]
            finally:
                conn.close()
            payload["database"] = {"reachable": True, "user_version": user_version}
        except sqlite3.Error:
            payload["status"] = "degraded"
        failure = last_failure(config.database_path)
        if failure is not None:
            # 截断错误文本，避免堆栈类内容撑爆响应或泄露内部细节
            failure = {**failure, "error": failure["error"][:200]}
        payload["last_failure"] = failure
        return payload

    app.include_router(build_auth_router(config.web_token, sessions), prefix="/api/v1")
    app.include_router(
        build_api_router(
            config.database_path,
            config.config_path,
            config=config,
            client=client,
            conn=conn,
            chat_names=chat_names,
        ),
        prefix="/api/v1",
    )
    if _DIST.is_dir():
        app.mount("/", StaticFiles(directory=_DIST, html=True), name="web")
    return app
