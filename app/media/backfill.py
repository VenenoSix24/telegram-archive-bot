"""存量缩略图补抓：遍历缺缩略图的已归档媒体消息，逐个下载。

V2 W2 数据扩展的一环：老库在缩略图功能上线前归档的消息没有 thumb_path，
用一次补抓填上。限速用 forward_interval，避免触发 FloodWait（任务书 §40）。
"""

from __future__ import annotations

import asyncio
import logging

from app.config import Config
from app.media.thumbnails import ThumbnailCache, choose_thumbnail_message

logger = logging.getLogger(__name__)

_MEDIA_TYPES = ("photo", "video", "document")


async def backfill_thumbs(
    client,
    config: Config,
    conn,
    cache: ThumbnailCache,
    *,
    limit: int = 100,
) -> int:
    """给缺缩略图的已归档媒体消息补图，返回本次成功数量。

    只处理 status='archived' 且有媒体类型但 thumb_path 为空的消息；
    抓不到（源无缩略图/已删）则跳过，不阻塞后续。
    """
    rows = conn.execute(
        "SELECT m.id, m.source_chat_id, m.source_message_id "
        "FROM messages m "
        "WHERE m.status='archived' AND m.thumb_path IS NULL "
        "AND m.media_type IN (?, ?, ?) "
        "ORDER BY m.id LIMIT ?",
        (*_MEDIA_TYPES, limit),
    ).fetchall()
    if not rows:
        return 0

    done = 0
    for row in rows:
        try:
            chat = await client.get_entity(row["source_chat_id"])
            source = await client.get_messages(chat, ids=row["source_message_id"])
            if source is None:
                continue
            messages = [source]
            if source.grouped_id:
                messages = [
                    m
                    for m in await client.get_messages(chat, limit=200)
                    if m.grouped_id == source.grouped_id
                ]
                messages.sort(key=lambda m: m.id)
            selected = choose_thumbnail_message(
                messages, getattr(config, "thumbnail_media", "first_video")
            )
            path = await cache.fetch(
                client, selected, selected.id, chat_id=row["source_chat_id"]
            )
            if path is None:
                continue
            conn.execute(
                "UPDATE messages SET thumb_path=? WHERE id=?",
                (str(path), row["id"]),
            )
            conn.execute(
                "UPDATE message_targets SET thumb_path=? "
                "WHERE message_id=? AND thumb_path IS NULL",
                (str(path), row["id"]),
            )
            conn.commit()
            done += 1
        except Exception:
            logger.exception("backfill thumb failed for messages#%s", row["id"])
        await asyncio.sleep(max(config.forward_interval, 0.5))
    return done
