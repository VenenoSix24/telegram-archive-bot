"""Web API：/api/v1 下的读写端点。

读取端点（GET）开独立短连接、跑在 FastAPI 线程池，不碰主循环的连接；
编辑端点（PATCH）必须是 async、跑在事件循环上，才能直接复用主进程持有的
Telethon client 与共享 conn，完成「写 DB → 重渲染 → edit 目标消息 → 刷新
索引」的 Telegram 侧同步（任务书 §19 双向同步）。
"""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app.media.thumbnails import ThumbnailCache, choose_thumbnail_message
from app.processor.edit import apply_message_edit
from app.telegram.client import resolve_chat_name
from app.web.config_editor import apply_editable_config, read_editable_config
from app.web.backup import backup_config, backup_database, reset_database

logger = logging.getLogger(__name__)

COOKIE_NAME = "archive_session"

_QUEUE_COUNTS = "SELECT status, COUNT(*) AS n FROM queue GROUP BY status"


class PatchBody(BaseModel):
    target_id: int | None = None
    body: str | None = None
    body_html: str | None = None
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
    keys = row.keys()
    original_html = row["original_html"] if "original_html" in keys else ""
    try:
        target_rows = conn.execute(
            "SELECT id, target_chat_id, target_message_id, target_url, status, "
            "original_text, original_html, rendered_text, rating "
            "FROM message_targets WHERE message_id=? ORDER BY id",
            (row["id"],),
        )
    except sqlite3.OperationalError as exc:
        if "no such table: message_targets" not in str(exc):
            raise
        target_rows = []
    targets = []
    for target in target_rows:
        try:
            target_tag_rows = conn.execute(
                "SELECT t.name, tt.type FROM target_tags tt JOIN tags t ON t.id=tt.tag_id "
                "WHERE tt.target_id=? ORDER BY tt.type, t.name",
                (target["id"],),
            )
        except sqlite3.OperationalError as exc:
            if "no such table: target_tags" not in str(exc):
                raise
            target_tag_rows = []
        target_tags = [{"name": tag["name"], "type": tag["type"]} for tag in target_tag_rows]
        targets.append({
            "id": target["id"],
            "chat_id": target["target_chat_id"],
            "message_id": target["target_message_id"],
            "url": target["target_url"],
            "status": target["status"],
            "original_text": target["original_text"],
            "original_html": target["original_html"],
            "rendered_text": target["rendered_text"],
            "rating": target["rating"],
            "tags": target_tags,
        })
    if not targets and row["target_chat_id"] is not None:
        targets = [{
            "id": None,
            "chat_id": row["target_chat_id"],
            "message_id": row["target_message_id"],
            "url": row["target_url"],
            "status": row["status"],
        }]
    return {
        "id": row["id"],
        "material_id": row["id"],
        "source_chat_id": row["source_chat_id"],
        "source_message_id": row["source_message_id"],
        "target_chat_id": row["target_chat_id"],
        "target_message_id": row["target_message_id"],
        "media_type": row["media_type"],
        "media_group_id": row["media_group_id"],
        "original_text": row["original_text"],
        "original_html": original_html,
        "rendered_text": row["rendered_text"],
        "rating": row["rating"],
        "source_url": row["source_url"],
        "target_url": row["target_url"],
        "targets": targets,
        "file_name": row["file_name"],
        "file_size": row["file_size"],
        "duration": row["duration"],
        "status": row["status"],
        "created_at": row["created_at"],
        "tags": tags,
        "thumb": {"available": bool(row["thumb_path"]), "path": row["thumb_path"]},
    }


def _sql_filters(query) -> tuple[str, list]:
    """构造仍可直接映射到 messages 表的筛选条件。"""
    conds: list[str] = []
    params: list[object] = []
    media_type = query.get("media_type")
    if media_type:
        conds.append("media_type = ?")
        params.append(media_type)
    where = f"WHERE {' AND '.join(conds)}" if conds else ""
    return where, params


def _matches_message(message: dict, query, status: str = "all") -> bool:
    if status != "all":
        expected = "archived" if status == "active" else "deleted"
        if message["status"] != expected:
            return False
    rating = query.get("rating")
    if rating not in (None, "") and message["rating"] != int(rating):
        return False
    target = query.get("target_chat_id")
    if target and message["target_chat_id"] != int(target):
        return False
    text = query.get("q")
    searchable = f'{message["original_text"] or ""} {message["rendered_text"] or ""}'
    if text and text.lower() not in searchable.lower():
        return False
    tag = query.get("tag")
    if tag and tag not in {item["name"] for item in message["tags"]}:
        return False
    return True


def build_api_router(
    database_path: str,
    config_path: str | None = None,
    config=None,
    client=None,
    conn=None,
) -> APIRouter:
    router = APIRouter(dependencies=[Depends(_require_auth)])
    router._conn = conn

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
            try:
                target_rows = conn.execute(
                    "SELECT target_chat_id, COUNT(*) AS n FROM message_targets "
                    "WHERE status='archived' GROUP BY target_chat_id ORDER BY n DESC"
                ).fetchall()
            except sqlite3.OperationalError as exc:
                if "no such table: message_targets" not in str(exc):
                    raise
                target_rows = conn.execute(
                    "SELECT target_chat_id, COUNT(*) AS n FROM messages "
                    "WHERE target_chat_id IS NOT NULL GROUP BY target_chat_id ORDER BY n DESC"
                ).fetchall()
            targets = [
                {"chat_id": r["target_chat_id"], "count": r["n"]} for r in target_rows
            ]
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
            "targets": targets,
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
        request: Request, limit: int = 30, offset: int = 0, status: str = "active"
    ) -> dict:
        where, params = _sql_filters(request.query_params)
        if status not in {"active", "deleted", "all"}:
            raise HTTPException(status_code=400, detail="invalid status")
        with _connect(database_path) as conn:
            rows = conn.execute(
                f"SELECT * FROM messages {where} ORDER BY id DESC", params
            ).fetchall()
            expanded = []
            for row in rows:
                message = _message_dict(conn, row)
                if not message["targets"] or message["targets"][0].get("id") is None:
                    if _matches_message(message, request.query_params, status):
                        expanded.append(message)
                    continue
                for target in message["targets"]:
                    item = {
                        **message,
                        "id": message["id"],
                        "material_id": target["id"],
                        "target_id": target["id"],
                        "target_chat_id": target["chat_id"],
                        "target_message_id": target["message_id"],
                        "target_url": target["url"],
                        "status": target["status"],
                        "original_text": target["original_text"],
                        "original_html": target["original_html"],
                        "rendered_text": target["rendered_text"],
                        "rating": target["rating"],
                        "tags": target["tags"],
                        "targets": [target],
                    }
                    if _matches_message(item, request.query_params, status):
                        expanded.append(item)
            expanded.sort(key=lambda item: (item["material_id"], item["id"]), reverse=True)
            total = len(expanded)
            items = expanded[offset:offset + limit]
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
    async def message_thumb(message_id: int, request: Request, target_id: int | None = None):
        """返回消息缩略图；本地缺失且有 client 时懒抓并落库（计划书 D5 懒补）。"""
        with _connect(database_path) as conn:
            row = conn.execute(
                "SELECT * FROM messages WHERE id=?", (message_id,)
            ).fetchone()
            if row is None:
                raise HTTPException(status_code=404, detail="message not found")
            target_row = None
            if target_id is not None:
                try:
                    target_row = conn.execute(
                        "SELECT * FROM message_targets WHERE id=? AND message_id=?",
                        (target_id, message_id),
                    ).fetchone()
                except sqlite3.OperationalError:
                    target_row = None
                if target_row is None:
                    raise HTTPException(status_code=404, detail="target not found")
            existing = target_row["thumb_path"] if target_row else row["thumb_path"]

        path = Path(existing) if existing else None
        if path is not None and path.exists():
            return FileResponse(str(path), headers={"Cache-Control": "public, max-age=86400"})

        client = request.app.state.client
        if client is None:
            raise HTTPException(status_code=404, detail="thumbnail unavailable")
        with _connect(database_path) as conn:
            row = conn.execute("SELECT * FROM messages WHERE id=?", (message_id,)).fetchone()
        try:
            cache = ThumbnailCache()

            async def fetch_from(chat_id, telegram_message_id):
                if not chat_id or not telegram_message_id:
                    return None
                chat = await client.get_entity(chat_id)
                message = await client.get_messages(chat, ids=telegram_message_id)
                if message is None:
                    return None
                if message.grouped_id and config:
                    group = [
                        item for item in await client.get_messages(chat, limit=200)
                        if item.grouped_id == message.grouped_id
                    ]
                    group.sort(key=lambda item: item.id)
                    message = choose_thumbnail_message(group, config.thumbnail_media)
                return await cache.fetch(client, message, target_id or message_id)

            fetched = None
            if target_row:
                archive_chat_id = target_row["target_chat_id"]
                archive_message_id = target_row["target_message_id"]
            else:
                archive_chat_id = row["target_chat_id"]
                archive_message_id = row["target_message_id"]
            if config is None or config.thumbnail_source != "source":
                fetched = await fetch_from(archive_chat_id, archive_message_id)
            if fetched is None and (config is None or config.thumbnail_source != "archive"):
                fetched = await fetch_from(row["source_chat_id"], row["source_message_id"])

        except Exception:
            logger.exception("thumbnail fetch failed for messages#%s", message_id)
            fetched = None
        if fetched is None or not fetched.exists():
            raise HTTPException(status_code=404, detail="thumbnail unavailable")
        with _connect(database_path) as conn:
            conn.execute(
                "UPDATE message_targets SET thumb_path=? WHERE id=?",
                (str(fetched), target_id),
            ) if target_id is not None else conn.execute(
                "UPDATE messages SET thumb_path=? WHERE id=?", (str(fetched), message_id)
            )
            conn.commit()
        return FileResponse(str(fetched), headers={"Cache-Control": "public, max-age=86400"})

    @router.patch("/messages/{message_id}")
    async def patch_message(
        message_id: int,
        request: Request,
        body: PatchBody,
    ) -> dict:
        if (
            body.add_tags is None
            and body.remove_tag_names is None
            and body.rating is None
            and body.body is None
            and body.body_html is None
        ):
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
            target_id=body.target_id,
            body=body.body,
            body_html=body.body_html,
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

    if config_path is not None:
        @router.get("/config")
        async def get_config() -> dict:
            try:
                result = read_editable_config(Path(config_path))
                if client is not None:
                    for collection in (result["source_chats"], result["target_channels"]):
                        for item in collection:
                            if not item.get("name") and item.get("chat_id") is not None:
                                try:
                                    item["name"] = await resolve_chat_name(client, item["chat_id"])
                                except Exception:
                                    pass
                return result
            except Exception as exc:
                raise HTTPException(status_code=400, detail="config.yaml unreadable") from exc

        @router.post("/ops/backup")
        def backup_ops(body: dict) -> dict:
            kind = body.get("kind")
            path = Path(config_path)
            if kind == "config":
                result = backup_config(path)
            elif kind == "database":
                result = backup_database(Path(database_path))
            else:
                raise HTTPException(status_code=400, detail="invalid backup kind")
            return {"path": result.name}

        @router.post("/ops/reset-database")
        def reset_database_ops(body: dict) -> dict:
            if body.get("confirm") != "RESET DATABASE":
                raise HTTPException(status_code=400, detail="confirmation required")
            backup_database(Path(database_path))
            if getattr(router, "_conn", None) is None:
                raise HTTPException(status_code=503, detail="database connection unavailable")
            reset_database(router._conn)
            return {"ok": True}

        @router.put("/config")
        def put_config(body: dict) -> dict:
            try:
                return apply_editable_config(Path(config_path), dict(body))
            except Exception as exc:
                raise HTTPException(status_code=400, detail=f"config invalid: {exc}") from exc

    return router
