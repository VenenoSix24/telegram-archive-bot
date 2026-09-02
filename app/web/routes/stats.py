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

    @router.get("/tags")
    def list_tags() -> dict:
        with queries.open_connection(ctx.database_path) as conn:
            return queries.tag_counts(conn)

    return router
