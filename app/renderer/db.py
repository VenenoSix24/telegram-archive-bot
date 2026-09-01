"""消息记录与渲染的桥接：从 DB 组装渲染输入。"""

from __future__ import annotations

import json
import sqlite3

from app.renderer.render import render_message


def render_from_db(
    conn: sqlite3.Connection,
    message_row,
    *,
    rating_override: int | None = None,
    body_override: str | None = None,
) -> str:
    """按 messages 记录 + 关联 tags 渲染最终文本。

    rating_override 传入时用其替代记录中的 rating（/rating 变更场景）；
    body_override 用于相册非首条（original_text 为空时取组锚消息文字）。
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
    body = body_override if body_override is not None else (message_row["original_text"] or "")
    body_html = None
    if body_override is None and "original_html" in message_row.keys():
        body_html = message_row["original_html"] or None
    template_layout = None
    if "template_layout" in message_row.keys():
        try:
            template_layout = json.loads(message_row["template_layout"])
        except (TypeError, json.JSONDecodeError):
            template_layout = None
    return render_message(
        rating=message_row["rating"] if rating_override is None else rating_override,
        tags=tags,
        body=body,
        body_html=body_html,
        source_url=message_row["source_url"],
        template_layout=template_layout,
    )
