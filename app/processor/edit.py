"""编辑共享层：tag/rating 变更 → DB 重渲染 → edit 目标消息。

verify 双向同步的唯一入口（Telegram 命令与 Web API 均走这里）。
"""

from __future__ import annotations

import html as html_lib
import json
import re
import sqlite3

from telethon.errors import MessageNotModifiedError

from app.processor.ratings import update_rating
from app.processor.recorder import add_manual_tags, remove_tags
from app.renderer.render import render_message
from app.tags.engine import render_tags

_RATING_LINE_RE = re.compile(r"^推荐指数：⭐+$")


async def _telegram_edit(client, chat_id: int, message_id: int, rendered: str) -> None:
    try:
        await client.edit_message(chat_id, message_id, rendered, parse_mode="html")
    except MessageNotModifiedError:
        # 内容本就一致（如重复添加已有 Tag / 相同评级），视为成功
        pass
    except TypeError as exc:
        if "parse_mode" not in str(exc):
            raise
        await client.edit_message(chat_id, message_id, rendered)


def extract_edited_body(
    text: str, html_text: str, *, tags: list[str], source_url: str | None
) -> tuple[str, str]:
    """从 Telegram 编辑后的整条渲染消息中剥离模板骨架，只留正文。

    用户编辑的是「评级+Tag+正文+来源」的完整渲染结果，直接当正文回写会
    套娃。编辑习惯不可假设：可能在末尾追加（来源块之后）、也可能残留上
    一轮失败产生的脏骨架，因此骨架按内容精确匹配、全文任意位置移除——
    评级行允许星数增减，来源块兼容 Telegram 自动加链接实体后的 <a> 形态。
    代价：正文里恰好整行等于骨架的罕见内容会被一并移除。
    """
    plain_tag_line = render_tags(tags) if tags else ""
    html_tag_line = html_lib.escape(plain_tag_line) if tags else ""
    url_variants: set[str] = set()
    if source_url:
        escaped_url = html_lib.escape(source_url, quote=True)
        url_variants = {
            source_url,
            escaped_url,
            f'<a href="{escaped_url}">{escaped_url}</a>',
            f'<a href="{source_url}">{source_url}</a>',
        }

    def clean(lines: list[str], *, html: bool) -> list[str]:
        tag_line = html_tag_line if html else plain_tag_line
        kept: list[str] = []
        index = 0
        while index < len(lines):
            line = lines[index]
            if _RATING_LINE_RE.match(line) or (tag_line and line == tag_line):
                index += 1
                continue
            if (
                source_url
                and line == "来自："
                and index + 1 < len(lines)
                and lines[index + 1] in url_variants
            ):
                index += 2
                continue
            kept.append(line)
            index += 1
        # 折叠连续空行（移除骨架后遗留），再掐头去尾
        collapsed: list[str] = []
        for line in kept:
            if line == "" and (not collapsed or collapsed[-1] == ""):
                continue
            collapsed.append(line)
        while collapsed and collapsed[0] == "":
            collapsed.pop(0)
        while collapsed and collapsed[-1] == "":
            collapsed.pop()
        return collapsed

    body = "\n".join(clean(text.split("\n"), html=False)).strip()
    body_html = "\n".join(clean(html_text.split("\n"), html=True)).strip()
    return body, body_html


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
    try:
        template_layout = json.loads(target["template_layout"])
    except (IndexError, KeyError, TypeError, json.JSONDecodeError):
        template_layout = None
    rendered = render_message(
        rating=next_rating,
        tags=tags,
        body=next_body,
        body_html=next_body_html or None,
        source_url=row["source_url"],
        template_layout=template_layout,
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
