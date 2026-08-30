"""消息记录与渲染的桥接：从 DB 组装渲染输入。"""

from __future__ import annotations

import sqlite3

from app.renderer.render import render_message


def render_from_db(
    conn: sqlite3.Connection,
    message_row,
    *,
    rating_override: int | None = None,
) -> str:
    """按 messages 记录 + 关联 tags 渲染最终文本。

    rating_override 传入时用其替代 records 中的 rating（/rating 变更场景）。
    """
    tags = [
        row["name"]
        for row in conn.execute(
            "SELECT t.name FROM message_tags mt "
            "JOIN tags t ON t.id = mt.tag_id "
            "WHERE mt.message_id = ? ORDER BY mt.rowid",
            (message_row["id"],),
        )
    ]
    return render_message(
        rating=message_row["rating"] if rating_override is None else rating_override,
        tags=tags,
        body=message_row["original_text"] or "",
        source_url=message_row["source_url"],
    )
