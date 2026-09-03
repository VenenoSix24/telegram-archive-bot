"""概览端点：/health、/stats、/tags。"""

from __future__ import annotations

from fastapi import APIRouter

from app.web import queries
from app.web.routes.deps import WebContext


def build_router(ctx: WebContext) -> APIRouter:
    router = APIRouter()

    @router.get("/health")
    def health() -> dict:
        return {"status": "ok"}

    @router.get("/stats")
    def stats() -> dict:
        return queries.stats_body(
            ctx.database_path,
            config_path=ctx.config_path,
            chat_names=ctx.chat_names,
        )

    @router.get("/stats/trend")
    def stats_trend(days: int = 30) -> dict:
        """近 N 天归档趋势（?days=，缺省 30，服务端收敛到 1..90）。"""
        return queries.trend_body(ctx.database_path, days=days)

    @router.get("/tags")
    def list_tags() -> dict:
        with queries.open_connection(ctx.database_path) as conn:
            return queries.tag_counts(conn)

    return router
