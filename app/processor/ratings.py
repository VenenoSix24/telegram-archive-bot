"""Rating 数据操作：按目标频道消息定位、更新评级并重渲染。

Telegram 侧的 edit_message 调用在事件层（Phase 6 集成）完成，这里只负责
DB 一致性：update_rating 同步更新 messages.rating 与 rendered_text，
返回新文本供上层编辑频道消息。
"""

from __future__ import annotations

import sqlite3

from app.renderer.db import render_from_db


def find_message_by_target(conn: sqlite3.Connection, chat_id: int, message_id: int):
    """按目标频道消息定位 messages 记录；不存在返回 None。"""
    return conn.execute(
        "SELECT * FROM messages WHERE target_chat_id=? AND target_message_id=?",
        (chat_id, message_id),
    ).fetchone()


def update_rating(conn: sqlite3.Connection, message_id: int, value: int) -> str | None:
    """更新评级为 value（0~5）并重渲染，返回新的 rendered_text；记录不存在返回 None。"""
    row = conn.execute("SELECT * FROM messages WHERE id=?", (message_id,)).fetchone()
    if row is None:
        return None
    conn.execute("UPDATE messages SET rating=? WHERE id=?", (value, message_id))
    rendered = render_from_db(conn, row, rating_override=value)
    conn.execute("UPDATE messages SET rendered_text=? WHERE id=?", (rendered, message_id))
    conn.commit()
    return rendered
