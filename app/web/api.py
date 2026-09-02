"""Web API：/api/v1 读写端点组装。

读取端点（GET）开独立短连接、跑在 FastAPI 线程池，不碰主循环的连接；
编辑端点（PATCH）必须是 async、跑在事件循环上，才能直接复用主进程持有的
Telethon client 与共享 conn，完成「写 DB → 重渲染 → edit 目标消息 → 刷新
索引」的 Telegram 侧同步（任务书 §19 双向同步）。

端点实现按域拆在 routes/（messages/thumb/stats/config/ops），
SQL 查询集中在 queries.py，响应结构在 serializers.py。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.web.routes import config as config_routes
from app.web.routes import messages, ops, stats, thumb
from app.web.routes.deps import WebContext, require_auth


def build_api_router(
    database_path: str,
    config_path: str | None = None,
    config=None,
    client=None,
    conn=None,
    chat_names: dict[int, str] | None = None,
) -> APIRouter:
    """组装 /api/v1 路由；conn 为兼容旧签名保留（PATCH 用 app.state.conn）。"""
    del conn
    ctx = WebContext(
        database_path=database_path,
        config=config,
        config_path=config_path,
        client=client,
        chat_names=chat_names,
    )
    router = APIRouter(dependencies=[Depends(require_auth)])
    router.include_router(stats.build_router(ctx))
    router.include_router(messages.build_router(ctx))
    router.include_router(thumb.build_router(ctx))
    if config_path is not None:
        router.include_router(config_routes.build_router(ctx))
        router.include_router(ops.build_router(ctx))
    return router
