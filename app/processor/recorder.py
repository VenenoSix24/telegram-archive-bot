"""把规范化后的 IncomingMessage 落库：messages + tags + message_tags。

Tag 合并规则（文档第 12/13 节）：source（来源群默认）→ original（原消息
hashtag，受 preserve_original 控制）→ manual（人工指令），去重保序；每条
消息记录来源类型到 message_tags。
"""

from __future__ import annotations

import sqlite3

from app.processor.adapter import IncomingMessage
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

    manual = manual_tags or []
    original = extract_hashtags(incoming.text) if preserve_original else []
    merged = merge_tags(list(source_tags), original, manual)

    conn.execute(
        "INSERT INTO messages (source_chat_id, source_message_id, media_type, "
        "media_group_id, original_text, source_url, status) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            incoming.source_chat_id,
            incoming.source_message_id,
            incoming.media_type or "text",
            incoming.media_group_id,
            incoming.text,
            incoming.source_url,
            status,
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
