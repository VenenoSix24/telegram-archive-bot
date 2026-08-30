"""归档发送：把已落库的消息复制到目标频道。

媒体以引用复用（send_file file=media），不下载到服务器再上传（ADR 0001/d、
spike 0002 验证）；Album 一次传 media list 保持分组与顺序。本函数即
Queue 的 sender 接口，收到 message_id 后从 DB 读记录执行复制并回填 target。
"""

from __future__ import annotations

import logging
import sqlite3

from app.renderer.db import render_from_db

logger = logging.getLogger(__name__)

_ALBUM_SCAN_LIMIT = 200


async def _fetch_source_messages(client, chat, row: sqlite3.Row) -> list:
    """取源消息；若是 Album，额外收集同组媒体消息（v1 扫描最近消息实现）。"""
    first = await client.get_messages(chat, ids=row["source_message_id"])
    if first is None:
        raise FileNotFoundError(
            f"源消息已删除或不可访问: chat={row['source_chat_id']} msg={row['source_message_id']}"
        )
    if not first.grouped_id:
        return [first]
    recent = await client.get_messages(chat, limit=_ALBUM_SCAN_LIMIT)
    grouped = [m for m in recent if m.grouped_id == first.grouped_id]
    if not grouped:
        return [first]
    return sorted(grouped, key=lambda m: m.id)


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
    rendered = render_from_db(conn, row)
    target = await client.get_entity(config.target_channel_id)

    medias = [m.media for m in msgs if m.media]
    if medias:
        sent = await client.send_file(target, file=medias, caption=rendered)
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
