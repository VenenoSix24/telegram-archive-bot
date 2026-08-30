"""归档发送：把已落库的消息复制到目标频道。

媒体以引用复用（send_file file=media），不下载到服务器再上传（ADR 0001/d、
spike 0002 验证）；Album 一次传 media list 保持分组与顺序。本函数即
Queue 的 sender 接口，收到 message_id 后从 DB 读记录执行复制并回填 target。
"""

from __future__ import annotations

import logging
import sqlite3
from io import BytesIO

from telethon.tl.types import MessageMediaDocument

from app.renderer.db import render_from_db

logger = logging.getLogger(__name__)

_ALBUM_SCAN_LIMIT = 200


async def collect_album(client, chat, first_message) -> list:
    """收集同一相册的全部消息（按 id 升序，首条为锚）；非相册返回 [first_message]。

    v1 用扫描最近消息的方式实现分组（相册通常刚发生，limit 内即可覆盖）。
    """
    if not first_message.grouped_id:
        return [first_message]
    recent = await client.get_messages(chat, limit=_ALBUM_SCAN_LIMIT)
    grouped = [m for m in recent if m.grouped_id == first_message.grouped_id]
    return sorted(grouped, key=lambda m: m.id) or [first_message]


async def _fetch_source_messages(client, chat, row: sqlite3.Row) -> list:
    first = await client.get_messages(chat, ids=row["source_message_id"])
    if first is None:
        raise FileNotFoundError(
            f"源消息已删除或不可访问: chat={row['source_chat_id']} msg={row['source_message_id']}"
        )
    return await collect_album(client, chat, first)


def _save_target(
    conn: sqlite3.Connection,
    message_id: int,
    *,
    target_chat_id: int,
    target_message_id: int,
    target_url: str | None,
) -> None:
    conn.execute(
        "UPDATE messages SET target_chat_id=?, target_message_id=?, target_url=?, "
        "status='archived' WHERE id=?",
        (target_chat_id, target_message_id, target_url, message_id),
    )
    conn.commit()


async def _source_thumb(client, first_message) -> tuple[str, bytes] | None:
    """视频/文档缩略图随附：下载 KB 级缩略图，避免目标频道黑图。

    引用复制媒体时 Telegram 服务端不会为复制出的消息生成缩略图，需带源
    缩略图。仅对带缩略图的单条文档生效；相册多图不受影响（图即缩略图）。
    """
    media = first_message.media
    if not isinstance(media, MessageMediaDocument):
        return None
    if not getattr(media.document, "thumbs", None):
        return None
    try:
        buf = BytesIO()
        await client.download_media(first_message, file=buf, thumb=-1)
        return ("thumb.jpg", buf.getvalue())
    except Exception:
        logger.debug("thumb download failed for msg %s", first_message.id)
        return None


async def archive_message_by_db_id(
    client,
    config,
    conn: sqlite3.Connection,
    message_id: int,
) -> int:
    """按 messages 记录复制到目标频道并回填 DB，返回目标频道首条消息 id。

    供 Queue sender（Phase 8）调用；发送失败向上抛，由 Queue 处理重试。
    """
    row = conn.execute("SELECT * FROM messages WHERE id=?", (message_id,)).fetchone()
    if row is None:
        raise KeyError(f"messages id={message_id} not found")

    chat = await client.get_entity(row["source_chat_id"])
    msgs = await _fetch_source_messages(client, chat, row)
    # 相册组文字挂在组内最早消息上：本条正文为空时用锚消息文字渲染（避免缺 caption）。
    body_override = None
    if row["media_group_id"] and msgs:
        anchor_text = msgs[0].message or ""
        if not row["original_text"] and anchor_text:
            body_override = anchor_text
    rendered = render_from_db(conn, row, body_override=body_override)
    target = await client.get_entity(config.target_channel_id)

    medias = [m.media for m in msgs if m.media]
    if medias:
        send_kwargs: dict = {}
        if len(medias) == 1:
            thumb = await _source_thumb(client, msgs[0])
            if thumb:
                send_kwargs["thumb"] = thumb
        sent = await client.send_file(
            target, file=medias, caption=rendered, **send_kwargs
        )
        sent_list = sent if isinstance(sent, list) else [sent]
    else:
        sent_msg = await client.send_message(target, rendered)
        sent_list = [sent_msg]

    first = sent_list[0]
    username = getattr(target, "username", None)
    target_url = f"https://t.me/{username}/{first.id}" if username else None
    _save_target(
        conn,
        message_id,
        target_chat_id=config.target_channel_id,
        target_message_id=first.id,
        target_url=target_url,
    )
    logger.info(
        "archived messages#%s -> target msg %s (media=%s)",
        message_id,
        first.id,
        len(medias),
    )
    return first.id
