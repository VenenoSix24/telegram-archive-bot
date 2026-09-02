"""缩略图端点：GET /messages/{id}/thumb（本地命中直返，缺失懒抓落库）。"""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse

from app.media.thumbnails import ThumbnailCache, choose_thumbnail_message, thumbs_dir_for
from app.web import queries
from app.web.routes.deps import WebContext

logger = logging.getLogger(__name__)


def build_router(ctx: WebContext) -> APIRouter:
    router = APIRouter()

    @router.get("/messages/{message_id}/thumb")
    async def message_thumb(message_id: int, request: Request, target_id: int | None = None):
        """返回消息缩略图；本地缺失且有 client 时懒抓并落库（计划书 D5 懒补）。"""
        with queries.open_connection(ctx.database_path) as conn:
            row = queries.get_message_row(conn, message_id)
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
        with queries.open_connection(ctx.database_path) as conn:
            row = queries.get_message_row(conn, message_id)
        try:
            cache = ThumbnailCache(thumbs_dir_for(ctx.database_path))

            async def fetch_from(chat_id, telegram_message_id):
                if not chat_id or not telegram_message_id:
                    return None
                chat = await client.get_entity(chat_id)
                message = await client.get_messages(chat, ids=telegram_message_id)
                if message is None:
                    return None
                if message.grouped_id and ctx.config:
                    group = [
                        item for item in await client.get_messages(chat, limit=200)
                        if item.grouped_id == message.grouped_id
                    ]
                    group.sort(key=lambda item: item.id)
                    message = choose_thumbnail_message(group, ctx.config.thumbnail_media)
                return await cache.fetch(
                    client, message, telegram_message_id, chat_id=chat_id
                )

            fetched = None
            if target_row:
                archive_chat_id = target_row["target_chat_id"]
                archive_message_id = target_row["target_message_id"]
            else:
                archive_chat_id = row["target_chat_id"]
                archive_message_id = row["target_message_id"]
            if ctx.config is None or ctx.config.thumbnail_source != "source":
                fetched = await fetch_from(archive_chat_id, archive_message_id)
            if fetched is None and (ctx.config is None or ctx.config.thumbnail_source != "archive"):
                fetched = await fetch_from(row["source_chat_id"], row["source_message_id"])

        except Exception:
            logger.exception("thumbnail fetch failed for messages#%s", message_id)
            fetched = None
        if fetched is None or not fetched.exists():
            raise HTTPException(status_code=404, detail="thumbnail unavailable")
        with queries.open_connection(ctx.database_path) as conn:
            if target_id is not None:
                conn.execute(
                    "UPDATE message_targets SET thumb_path=? WHERE id=?",
                    (str(fetched), target_id),
                )
            else:
                conn.execute(
                    "UPDATE messages SET thumb_path=? WHERE id=?",
                    (str(fetched), message_id),
                )
            conn.commit()
        return FileResponse(str(fetched), headers={"Cache-Control": "public, max-age=86400"})

    return router
