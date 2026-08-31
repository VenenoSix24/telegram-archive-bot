"""归档发送：把已落库的消息复制到目标频道。

媒体以引用复用（send_file file=media），不下载到服务器再上传（ADR 0001/d、
spike 0002 验证）；Album 一次传 media list 保持分组与顺序。本函数即
Queue 的 sender 接口，收到 message_id 后从 DB 读记录执行复制并回填 target。

注意（平台硬限制）：引用复制视频时 Telegram 不会为新消息生成封面，而
Telethon 的 thumb 参数只在「上传新文件」路径生效、mtproto 的
InputMediaDocument 也没有 thumb 字段——因此引用复制的视频无法附加封面，
部分无封面视频在客户端显示为黑色缩略图。要带封面只能重新上传视频本体，
违背「不下载重传」原则，故不采纳。
"""

from __future__ import annotations

import logging
import sqlite3

from telethon import utils

from app.media.thumbnails import ThumbnailCache, choose_thumbnail_message
from app.processor.adapter import build_source_url
from app.renderer.db import render_from_db

logger = logging.getLogger(__name__)

_ALBUM_SCAN_LIMIT = 200
_THUMB_CACHE = ThumbnailCache()


def _input_media_with_cover(message):
    media = message.media
    cover = getattr(media, "video_cover", None)
    document = getattr(media, "document", None)
    if document is None or cover is None:
        return media
    converted = utils.get_input_media(document)
    converted.video_cover = utils.get_input_photo(cover)
    return converted


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
    thumb_path: str | None,
) -> None:
    conn.execute(
        "UPDATE messages SET target_chat_id=?, target_message_id=?, target_url=?, "
        "status='archived', thumb_path=? WHERE id=?",
        (target_chat_id, target_message_id, target_url, thumb_path, message_id),
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
    # 相册组文字挂在组内最早消息上：本条正文为空时用锚消息文字渲染（避免缺 caption）。
    body_override = None
    if row["media_group_id"] and msgs:
        anchor_text = msgs[0].message or ""
        if not row["original_text"] and anchor_text:
            body_override = anchor_text
    rendered = render_from_db(conn, row, body_override=body_override)
    target_id = config.target_for(row["source_chat_id"])
    target = await client.get_entity(target_id)

    medias = [m.media for m in msgs if m.media]
    if medias:
        media_inputs = [_input_media_with_cover(m) for m in msgs if m.media]
        sent = await client.send_file(
            target, file=media_inputs, caption=rendered, parse_mode="html"
        )
        sent_list = sent if isinstance(sent, list) else [sent]
    else:
        sent_msg = await client.send_message(target, rendered, parse_mode="html")
        sent_list = [sent_msg]

    first = sent_list[0]
    # 归档消息链接：公开频道 t.me/<名称>/<id>，私密频道 t.me/c/<内部id>/<id>
    #（与源链接同套逻辑，见 build_source_url）。
    target_url = build_source_url(target, first.id)
    # 归档成功后再抓缩略图（引用复制拿到的是原始 media，可正常下载小图）。
    thumb_message = choose_thumbnail_message(msgs, config.thumbnail_media)
    thumb_path = None
    if thumb_message:
        thumb = await _THUMB_CACHE.fetch(client, thumb_message, message_id)
        if thumb is not None:
            thumb_path = str(thumb)
    _save_target(
        conn,
        message_id,
        target_chat_id=target_id,
        target_message_id=first.id,
        target_url=target_url,
        thumb_path=thumb_path,
    )
    logger.info(
        "archived messages#%s -> target msg %s (media=%s)",
        message_id,
        first.id,
        len(medias),
    )
    return first.id
