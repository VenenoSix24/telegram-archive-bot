"""把规范化后的 IncomingMessage 落库：messages + tags + message_tags。

Tag 合并规则（文档第 12/13 节）：source（来源群默认）→ original（原消息
hashtag，受 preserve_original 控制）→ manual（人工指令），去重保序；每条
消息记录来源类型到 message_tags。
"""

from __future__ import annotations

import sqlite3

from app.processor.adapter import IncomingMessage
from app.renderer.db import render_from_db
from app.tags.engine import extract_hashtags, merge_tags


def _tag_source_type(manual: list[str], original: list[str], tag: str) -> str:
    if tag in manual:
        return "manual"
    if tag in original:
        return "original"
    return "source"


def record_message(
    conn: sqlite3.Connection,
    incoming: IncomingMessage,
    *,
    source_tags: list[str],
    preserve_original: bool,
    manual_tags: list[str] | None = None,
    status: str = "new",
) -> int | None:
    """写入一条源消息记录并关联 tags；来源已存在（去重）时返回 None。"""
    row = conn.execute(
        "SELECT id FROM messages WHERE source_chat_id=? AND source_message_id=?",
        (incoming.source_chat_id, incoming.source_message_id),
    ).fetchone()
    if row is not None:
        return None
    # 相册组级去重：同组已有记录则跳过，避免整组媒体重复归档（ADR 0002）。
    if incoming.media_group_id:
        group_row = conn.execute(
            "SELECT id FROM messages WHERE source_chat_id=? AND media_group_id=?",
            (incoming.source_chat_id, incoming.media_group_id),
        ).fetchone()
        if group_row is not None:
            return None

    manual = manual_tags or []
    original = extract_hashtags(incoming.text) if preserve_original else []
    merged = merge_tags(list(source_tags), original, manual)

    conn.execute(
        "INSERT INTO messages (source_chat_id, source_message_id, media_type, "
        "media_group_id, original_text, source_url, status, file_name, file_size, duration) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            incoming.source_chat_id,
            incoming.source_message_id,
            incoming.media_type or "text",
            incoming.media_group_id,
            incoming.text,
            incoming.source_url,
            status,
            incoming.file_name or "",
            incoming.file_size,
            incoming.duration,
        ),
    )
    message_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    for tag in merged:
        conn.execute(
            "INSERT OR IGNORE INTO tags (name, normalized_name) VALUES (?, ?)",
            (tag, tag.lower()),
        )
        tag_id = conn.execute("SELECT id FROM tags WHERE name=?", (tag,)).fetchone()["id"]
        conn.execute(
            "INSERT OR IGNORE INTO message_tags (message_id, tag_id, type) VALUES (?, ?, ?)",
            (message_id, tag_id, _tag_source_type(manual, original, tag)),
        )

    conn.commit()
    return message_id


def add_manual_tags(
    conn: sqlite3.Connection, message_id: int, manual_tags: list[str]
) -> str | None:
    """追加人工 tag 并重渲染，返回新 rendered_text；记录不存在返回 None。

    已存在同名 tag 不重复；新 tag 以 manual 类型入 message_tags，原有
    source/original 类型保持不变（Phase 7 回复补 tag）。
    """
    if not manual_tags:
        return None
    row = conn.execute("SELECT * FROM messages WHERE id=?", (message_id,)).fetchone()
    if row is None:
        return None
    existing = conn.execute(
        "SELECT t.name, mt.type FROM message_tags mt "
        "JOIN tags t ON t.id = mt.tag_id "
        "WHERE mt.message_id = ? ORDER BY mt.rowid",
        (message_id,),
    ).fetchall()
    type_of = {r["name"]: r["type"] for r in existing}
    new_only = [t for t in manual_tags if t not in type_of]
    merged = merge_tags([], list(type_of), new_only)

    conn.execute("DELETE FROM message_tags WHERE message_id=?", (message_id,))
    for tag in merged:
        conn.execute(
            "INSERT OR IGNORE INTO tags (name, normalized_name) VALUES (?, ?)",
            (tag, tag.lower()),
        )
        tag_id = conn.execute("SELECT id FROM tags WHERE name=?", (tag,)).fetchone()["id"]
        conn.execute(
            "INSERT INTO message_tags (message_id, tag_id, type) VALUES (?, ?, ?)",
            (message_id, tag_id, type_of.get(tag, "manual")),
        )

    rendered = render_from_db(conn, row)
    conn.execute("UPDATE messages SET rendered_text=? WHERE id=?", (rendered, message_id))
    conn.commit()
    return rendered
