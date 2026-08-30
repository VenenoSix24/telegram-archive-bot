"""Web API：/api/v1 下的读取端点。

Web 与 Telegram 共享同一 SQLite（WAL），这里的端点每次请求开独立短连接，
不碰主事件循环持有的连接，避免跨线程使用 sqlite3 连接。
"""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Request

COOKIE_NAME = "archive_session"

_QUEUE_COUNTS = "SELECT status, COUNT(*) AS n FROM queue GROUP BY status"


def _connect(database_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(database_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def _require_auth(request: Request) -> None:
    sid = request.cookies.get(COOKIE_NAME)
    sessions = request.app.state.sessions
    if not sessions.valid(sid):
        raise HTTPException(status_code=401, detail="unauthorized")


def build_api_router(database_path: str) -> APIRouter:
    router = APIRouter(dependencies=[Depends(_require_auth)])

    @router.get("/health")
    def health() -> dict:
        return {"status": "ok"}

    @router.get("/stats")
    def stats() -> dict:
        with _connect(database_path) as conn:
            total = conn.execute("SELECT COUNT(*) AS n FROM messages").fetchone()["n"]
            archived = conn.execute(
                "SELECT COUNT(*) AS n FROM messages WHERE status='archived'"
            ).fetchone()["n"]
            sources = conn.execute(
                "SELECT COUNT(DISTINCT source_chat_id) AS n FROM messages"
            ).fetchone()["n"]
            by_type = {
                row["media_type"]: row["n"]
                for row in conn.execute(
                    "SELECT media_type, COUNT(*) AS n FROM messages GROUP BY media_type"
                )
            }
            tag_rows = conn.execute(
                "SELECT COUNT(DISTINCT tag_id) AS n FROM message_tags"
            ).fetchone()["n"]
            tags = conn.execute("SELECT COUNT(*) AS n FROM tags").fetchone()["n"]
        queue = {"pending": 0, "processing": 0, "success": 0, "failed": 0}
        with _connect(database_path) as conn:
            for row in conn.execute(_QUEUE_COUNTS):
                queue[row["status"]] = row["n"]
        return {
            "messages": {
                "total": total,
                "archived": archived,
                "sources": sources,
                "by_type": by_type,
            },
            "tags": {"total": tags, "with_messages": tag_rows},
            "queue": queue,
        }

    return router
