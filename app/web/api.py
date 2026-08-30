"""Web API：/api/v1 下的读写端点。

读取端点（GET）开独立短连接、跑在 FastAPI 线程池，不碰主循环的连接；
编辑端点（PATCH）必须是 async、跑在事件循环上，才能直接复用主进程持有的
Telethon client 与共享 conn，完成「写 DB → 重渲染 → edit 目标消息 → 刷新
索引」的 Telegram 侧同步（任务书 §19 双向同步）。
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app.media.thumbnails import ThumbnailCache
from app.processor.edit import apply_message_edit

COOKIE_NAME = "archive_session"

_QUEUE_COUNTS = "SELECT status, COUNT(*) AS n FROM queue GROUP BY status"


class PatchBody(BaseModel):
    add_tags: list[str] | None = None
    remove_tag_names: list[str] | None = None
    rating: int | None = Field(default=None, ge=0, le=5)


def _connect(database_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(database_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def _require_auth(request: Request) -> None:
    sid = request.cookies.get(COOKIE_NAME)
    sessions = request.app.state.sessions
    if not sessions.valid(sid):
        raise HTTPException(status_code=401, detail="unauthorized")


def _message_dict(conn: sqlite3.Connection, row) -> dict:
    tags = [
        {"name": t["name"], "type": t["type"]}
        for t in conn.execute(
            "SELECT t.name, mt.type FROM message_tags mt "
            "JOIN tags t ON t.id = mt.tag_id "
            "WHERE mt.message_id = ? ORDER BY mt.type, t.name",
            (row["id"],),
        )
    ]
    return {
        "id": row["id"],
        "source_chat_id": row["source_chat_id"],
        "source_message_id": row["source_message_id"],
        "target_chat_id": row["target_chat_id"],
        "target_message_id": row["target_message_id"],
        "media_type": row["media_type"],
        "media_group_id": row["media_group_id"],
        "original_text": row["original_text"],
        "rendered_text": row["rendered_text"],
        "rating": row["rating"],
        "source_url": row["source_url"],
        "target_url": row["target_url"],
        "file_name": row["file_name"],
        "file_size": row["file_size"],
        "duration": row["duration"],
        "status": row["status"],
        "created_at": row["created_at"],
        "tags": tags,
        "thumb": {"available": bool(row["thumb_path"]), "path": row["thumb_path"]},
    }


def _sql_filters(query) -> tuple[str, list]:
    """查询参数 → (WHERE 子句骨架, 参数)；只允许白名单字段。

    q 走 original_text / rendered_text LIKE；tag 通过 message_tags 关联过滤。
    全部参数化，杜绝注入。
    """
    conds: list[str] = []
    params: list[object] = []
    media_type = query.get("media_type")
    if media_type:
        conds.append("media_type = ?")
        params.append(media_type)
    rating = query.get("rating")
    if rating not in (None, ""):
        conds.append("rating = ?")
        params.append(int(rating))
    source = query.get("source_chat_id")
    if source:
        conds.append("source_chat_id = ?")
        params.append(int(source))
    q = query.get("q")
    if q:
        conds.append("(original_text LIKE ? OR rendered_text LIKE ?)")
        params.extend((f"%{q}%", f"%{q}%"))
    tag = query.get("tag")
    if tag:
        conds.append("id IN (SELECT message_id FROM message_tags mt "
                     "JOIN tags tg ON tg.id = mt.tag_id WHERE tg.name = ?)")
        params.append(tag)
    where = f"WHERE {' AND '.join(conds)}" if conds else ""
    return where, params


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

    @router.get("/tags")
    def list_tags() -> dict:
        with _connect(database_path) as conn:
            rows = conn.execute(
                "SELECT t.name, t.normalized_name, COUNT(mt.message_id) AS count "
                "FROM tags t LEFT JOIN message_tags mt ON mt.tag_id = t.id "
                "GROUP BY t.id ORDER BY count DESC, t.name"
            ).fetchall()
        return {
            "items": [
                {"name": r["name"], "count": r["count"]} for r in rows
            ],
            "total": len(rows),
        }

    @router.get("/messages")
    def list_messages(
        request: Request, limit: int = 30, offset: int = 0
    ) -> dict:
        where, params = _sql_filters(request.query_params)
        with _connect(database_path) as conn:
            total = conn.execute(
                f"SELECT COUNT(*) AS n FROM messages {where}", params
            ).fetchone()["n"]
            rows = conn.execute(
                f"SELECT * FROM messages {where} ORDER BY id DESC "
                "LIMIT ? OFFSET ?",
                [*params, limit, offset],
            ).fetchall()
            items = [_message_dict(conn, r) for r in rows]
        return {"items": items, "total": total, "limit": limit, "offset": offset}

    @router.get("/messages/{message_id}")
    def get_message(message_id: int) -> dict:
        with _connect(database_path) as conn:
            row = conn.execute(
                "SELECT * FROM messages WHERE id=?", (message_id,)
            ).fetchone()
            if row is None:
                raise HTTPException(status_code=404, detail="message not found")
            return _message_dict(conn, row)

    @router.get("/messages/{message_id}/thumb")
    async def message_thumb(message_id: int, request: Request):
        """返回消息缩略图；本地缺失且有 client 时懒抓并落库（计划书 D5 懒补）。"""
        with _connect(database_path) as conn:
            row = conn.execute(
                "SELECT * FROM messages WHERE id=?", (message_id,)
            ).fetchone()
            if row is None:
                raise HTTPException(status_code=404, detail="message not found")
            existing = row["thumb_path"]

        path = Path(existing) if existing else None
        if path is not None and path.exists():
            return FileResponse(str(path))

        client = request.app.state.client
        if client is None:
            raise HTTPException(status_code=404, detail="thumbnail unavailable")
        # 当前 Web 只有 read 端点不碰 conn；懒抓用独立短连接补写 thumb_path。
        with _connect(database_path) as conn:
            row = conn.execute(
                "SELECT * FROM messages WHERE id=?", (message_id,)
            ).fetchone()
        try:
            chat = await client.get_entity(row["source_chat_id"])
            source = await client.get_messages(chat, ids=row["source_message_id"])
            fetched = (
                await ThumbnailCache().fetch(client, source, message_id)
                if source is not None
                else None
            )
        except Exception:
            fetched = None
        if fetched is None or not fetched.exists():
            raise HTTPException(status_code=404, detail="thumbnail unavailable")
        with _connect(database_path) as conn:
            conn.execute(
                "UPDATE messages SET thumb_path=? WHERE id=?", (str(fetched), message_id)
            )
            conn.commit()
        return FileResponse(str(fetched))

    @router.patch("/messages/{message_id}")
    async def patch_message(
        message_id: int,
        request: Request,
        body: PatchBody,
    ) -> dict:
        if body.add_tags is None and body.remove_tag_names is None and body.rating is None:
            raise HTTPException(status_code=422, detail="nothing to change")
        client = request.app.state.client
        conn = request.app.state.conn
        indexer = request.app.state.indexer
        if client is None or conn is None:
            raise HTTPException(status_code=503, detail="telegram client not available")
        ok = await apply_message_edit(
            client,
            conn,
            message_id,
            add_tags=body.add_tags,
            remove_tag_names=body.remove_tag_names,
            rating=body.rating,
            indexer=indexer,
        )
        if not ok:
            raise HTTPException(status_code=404, detail="message not found or not archived")
        with _connect(database_path) as db:
            row = db.execute(
                "SELECT * FROM messages WHERE id=?", (message_id,)
            ).fetchone()
            return _message_dict(db, row)

    return router
