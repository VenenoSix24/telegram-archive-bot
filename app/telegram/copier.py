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

import asyncio
import logging
import sqlite3

from telethon import utils

from app.media.thumbnails import (
    ThumbnailCache,
    choose_thumbnail_message,
    thumbs_dir_for,
)
from app.processor.adapter import build_source_url
from app.renderer.db import render_from_db

logger = logging.getLogger(__name__)

_ALBUM_SCAN_LIMIT = 200
# 相册成员"到齐"判定：计数静默 quiet 秒视为到齐，最长等 max_wait 秒
_SETTLE_QUIET = 0.8
_SETTLE_MAX = 4.0


def _input_media_with_cover(message):
    media = message.media
    cover = getattr(media, "video_cover", None)
    document = getattr(media, "document", None)
    if document is None or cover is None:
        return media
    converted = utils.get_input_media(document)
    converted.video_cover = utils.get_input_photo(cover)
    return converted


def _group_member_ids(
    conn: sqlite3.Connection, source_chat_id: int, grouped_id
) -> list[int] | None:
    """落库的相组成员 id 列表（升序）；无记录（旧数据）返回 None。"""
    rows = conn.execute(
        "SELECT source_message_id FROM media_group_members "
        "WHERE source_chat_id=? AND grouped_id=? ORDER BY source_message_id",
        (source_chat_id, str(grouped_id)),
    ).fetchall()
    return [row["source_message_id"] for row in rows] if rows else None


async def _wait_group_settled(
    conn: sqlite3.Connection, source_chat_id: int, grouped_id
) -> None:
    """等相组成员到齐：组员先后到达，锚点刚入队就被归档会拆散相册。

    成员计数在 quiet 秒内无新增即认为到齐；总时长不超过 max_wait。
    """
    deadline = asyncio.get_running_loop().time() + _SETTLE_MAX
    last = len(_group_member_ids(conn, source_chat_id, grouped_id) or [])
    while True:
        await asyncio.sleep(_SETTLE_QUIET)
        current = len(_group_member_ids(conn, source_chat_id, grouped_id) or [])
        if current == last or asyncio.get_running_loop().time() >= deadline:
            return
        last = current


async def collect_album(
    client,
    chat,
    first_message,
    *,
    conn: sqlite3.Connection | None = None,
    source_chat_id: int | None = None,
) -> list:
    """收集同一相册的全部消息（按 id 升序，首条为锚）；非相册返回 [first_message]。

    组成员优先取落库记录（到达时逐条记录，不受队列积压影响）；旧数据
    无记录时回退扫描最近消息（v1 行为，窗口外会拆散）。取成员前等计数
    稳定，避免锚点刚入队、组员还没到齐就被归档。
    """
    if not first_message.grouped_id:
        return [first_message]
    if conn is not None and source_chat_id is not None:
        await _wait_group_settled(conn, source_chat_id, first_message.grouped_id)
        member_ids = _group_member_ids(conn, source_chat_id, first_message.grouped_id)
        if member_ids:
            fetched = await client.get_messages(chat, ids=member_ids)
            grouped = sorted(
                (m for m in fetched if m is not None), key=lambda m: m.id
            )
            if grouped:
                return grouped
        # 旧数据无成员记录 → 回退扫描
    recent = await client.get_messages(chat, limit=_ALBUM_SCAN_LIMIT)
    grouped = [m for m in recent if m.grouped_id == first_message.grouped_id]
    return sorted(grouped, key=lambda m: m.id) or [first_message]


async def _fetch_source_messages(client, chat, row: sqlite3.Row, conn: sqlite3.Connection) -> list:
    first = await client.get_messages(chat, ids=row["source_message_id"])
    if first is None:
        raise FileNotFoundError(
            f"源消息已删除或不可访问: chat={row['source_chat_id']} msg={row['source_message_id']}"
        )
    return await collect_album(
        client, chat, first, conn=conn, source_chat_id=row["source_chat_id"]
    )


def _save_target(
    conn: sqlite3.Connection,
    message_id: int,
    *,
    target_chat_id: int,
    target_message_id: int,
    target_url: str | None,
    thumb_path: str | None,
    original_text: str,
    original_html: str,
    rendered_text: str,
    rating: int,
    template_layout: str,
) -> None:
    conn.execute(
        "INSERT INTO message_targets "
        "(message_id, target_chat_id, target_message_id, target_url, thumb_path, "
        "original_text, original_html, rendered_text, rating, template_layout, status) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'archived') "
        "ON CONFLICT(message_id, target_chat_id) DO UPDATE SET "
        "target_message_id=excluded.target_message_id, "
        "target_url=excluded.target_url, status='archived', "
        "thumb_path=COALESCE(excluded.thumb_path, message_targets.thumb_path), "
        "original_text=excluded.original_text, original_html=excluded.original_html, "
        "rendered_text=excluded.rendered_text, rating=excluded.rating, "
        "template_layout=excluded.template_layout",
        (
            message_id,
            target_chat_id,
            target_message_id,
            target_url,
            thumb_path,
            original_text,
            original_html,
            rendered_text,
            rating,
            template_layout,
        ),
    )
    target_row = conn.execute(
        "SELECT id FROM message_targets WHERE message_id=? AND target_chat_id=?",
        (message_id, target_chat_id),
    ).fetchone()
    conn.execute(
        "INSERT OR IGNORE INTO target_tags (target_id, tag_id, type) "
        "SELECT ?, tag_id, type FROM message_tags WHERE message_id=?",
        (target_row["id"], message_id),
    )
    conn.execute(
        "UPDATE messages SET target_chat_id=?, target_message_id=?, target_url=?, "
        "thumb_path=? WHERE id=? AND target_chat_id IS NULL",
        (target_chat_id, target_message_id, target_url, thumb_path, message_id),
    )
    conn.commit()


def _successful_targets(conn: sqlite3.Connection, message_id: int) -> set[int]:
    return {
        row["target_chat_id"]
        for row in conn.execute(
            "SELECT target_chat_id FROM message_targets "
            "WHERE message_id=? AND status='archived'",
            (message_id,),
        )
    }


async def archive_message_by_db_id(
    client,
    config,
    conn: sqlite3.Connection,
    message_id: int,
    chat_names: dict[int, str] | None = None,
) -> int:
    """按 messages 记录复制到所有目标频道并回填 DB。"""
    row = conn.execute("SELECT * FROM messages WHERE id=?", (message_id,)).fetchone()
    if row is None:
        raise KeyError(f"messages id={message_id} not found")

    chat = await client.get_entity(row["source_chat_id"])
    msgs = await _fetch_source_messages(client, chat, row, conn)
    # 相册组文字挂在组内最早消息上：本条正文为空时用锚消息文字渲染（避免缺 caption）。
    body_override = None
    if row["media_group_id"] and msgs:
        anchor_text = msgs[0].message or ""
        if not row["original_text"] and anchor_text:
            body_override = anchor_text
    rendered = render_from_db(conn, row, body_override=body_override)
    targets = config.targets_for(row["source_chat_id"])
    completed = _successful_targets(conn, message_id)
    target_ids = [target_id for target_id in targets if target_id not in completed]
    if not target_ids:
        return row["target_message_id"]

    first_target_message_id = row["target_message_id"]
    for target_id in target_ids:
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
        target_url = build_source_url(target, first.id)
        thumb_path = None
        thumb_message = choose_thumbnail_message(msgs, config.thumbnail_media)
        if thumb_message:
            thumb_cache = ThumbnailCache(thumbs_dir_for(config.database_path))
            thumb = await thumb_cache.fetch(
                client, thumb_message, thumb_message.id, chat_id=row["source_chat_id"]
            )
            if thumb is not None:
                thumb_path = str(thumb)
        _save_target(
            conn,
            message_id,
            target_chat_id=target_id,
            target_message_id=first.id,
            target_url=target_url,
            thumb_path=thumb_path,
            original_text=row["original_text"],
            original_html=row["original_html"] if "original_html" in row.keys() else "",
            rendered_text=rendered,
            rating=row["rating"],
            template_layout=(
                row["template_layout"]
                if "template_layout" in row.keys()
                else '["rating","tags","body","source"]'
            ),
        )
        if first_target_message_id is None:
            first_target_message_id = first.id
        target_name = (chat_names or {}).get(target_id, str(target_id))
        logger.info(
            "已归档到「%s」：消息 #%s（媒体 %s 个）",
            target_name,
            first.id,
            len(medias),
        )

    if _successful_targets(conn, message_id) >= set(targets):
        conn.execute("UPDATE messages SET status='archived' WHERE id=?", (message_id,))
        conn.commit()
    return first_target_message_id
