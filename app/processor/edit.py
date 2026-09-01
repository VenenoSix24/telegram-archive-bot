"""编辑共享层：tag/rating 变更 → DB 重渲染 → edit 目标消息。"""

from __future__ import annotations

import sqlite3

from app.processor.ratings import update_rating
from app.processor.recorder import add_manual_tags, remove_tags
from app.renderer.render import render_message


async def _telegram_edit(client, chat_id: int, message_id: int, rendered: str) -> None:
    try:
        await client.edit_message(chat_id, message_id, rendered, parse_mode="html")
    except TypeError as exc:
        if "parse_mode" not in str(exc):
            raise
        await client.edit_message(chat_id, message_id, rendered)


async def apply_message_edit(
    client,
    conn: sqlite3.Connection,
    message_id: int,
    *,
    target_id: int | None = None,
    body: str | None = None,
    body_html: str | None = None,
    add_tags: list[str] | None = None,
    remove_tag_names: list[str] | None = None,
    rating: int | None = None,
    indexer=None,
) -> bool:
    row = conn.execute("SELECT * FROM messages WHERE id=?", (message_id,)).fetchone()
    if row is None or not row["target_chat_id"]:
        return False

    if target_id is None:
        rendered = None
        if add_tags:
            rendered = add_manual_tags(conn, message_id, add_tags)
        if remove_tag_names:
            rendered = remove_tags(conn, message_id, remove_tag_names)
        if rating is not None:
            rendered = update_rating(conn, message_id, rating)
        if rendered is None:
            return False
        await _telegram_edit(client, row["target_chat_id"], row["target_message_id"], rendered)
        if indexer is not None:
            indexer.schedule()
        return True

    try:
        target = conn.execute(
            "SELECT * FROM message_targets WHERE id=? AND message_id=?",
            (target_id, message_id),
        ).fetchone()
    except sqlite3.OperationalError as exc:
        if "no such table: message_targets" not in str(exc):
            raise
        return False
    if target is None or target["status"] != "archived":
        return False
    if not (add_tags or remove_tag_names or rating is not None or body is not None):
        return False

    tags = [
        tag["name"]
        for tag in conn.execute(
            "SELECT t.name FROM target_tags tt JOIN tags t ON t.id=tt.tag_id "
            "WHERE tt.target_id=? ORDER BY tt.rowid",
            (target_id,),
        )
    ]
    for name in add_tags or []:
        if name not in tags:
            conn.execute(
                "INSERT OR IGNORE INTO tags (name, normalized_name) VALUES (?, ?)",
                (name, name.lower()),
            )
            tag_row = conn.execute("SELECT id FROM tags WHERE name=?", (name,)).fetchone()
            conn.execute(
                "INSERT OR IGNORE INTO target_tags "
                "(target_id, tag_id, type) VALUES (?, ?, 'manual')",
                (target_id, tag_row["id"]),
            )
            tags.append(name)
    if remove_tag_names:
        placeholders = ", ".join("?" for _ in remove_tag_names)
        conn.execute(
            f"DELETE FROM target_tags WHERE target_id=? AND tag_id IN "
            f"(SELECT id FROM tags WHERE name IN ({placeholders}))",
            [target_id, *remove_tag_names],
        )
        tags = [tag for tag in tags if tag not in remove_tag_names]

    next_rating = rating if rating is not None else target["rating"]
    next_body = body if body is not None else target["original_text"]
    next_body_html = target["original_html"] if body is None else body_html
    rendered = render_message(
        rating=next_rating,
        tags=tags,
        body=next_body,
        body_html=next_body_html or None,
        source_url=row["source_url"],
    )
    await _telegram_edit(client, target["target_chat_id"], target["target_message_id"], rendered)
    conn.execute(
        "UPDATE message_targets SET rating=?, original_text=?, original_html=?, rendered_text=? "
        "WHERE id=?",
        (next_rating, next_body, next_body_html or "", rendered, target_id),
    )
    conn.commit()
    if indexer is not None:
        indexer.schedule()
    return True
