"""共享编辑入口：tag/rating 变更 → DB → 重渲染 → edit 目标消息 → 刷新索引。

Telegram 回复命令（/tag /rating）与 Web API（PATCH /messages/{id}）走同一条
路径，保证两入口对同一 DB 的写入和渲染结果一致（任务书 §19：DB 是唯一
数据中心，Telegram 与 Web 都只是操作入口）。
"""

from __future__ import annotations

import sqlite3

from app.processor.ratings import update_rating
from app.processor.recorder import add_manual_tags, remove_tags


async def apply_message_edit(
    client,
    conn: sqlite3.Connection,
    message_id: int,
    *,
    add_tags: list[str] | None = None,
    remove_tag_names: list[str] | None = None,
    rating: int | None = None,
    indexer=None,
) -> bool:
    """应用一次编辑并同步目标频道的消息与置顶索引。

    至少一个动作存在才执行；目标消息缺失或渲染无变化返回 False。
    """
    row = conn.execute("SELECT * FROM messages WHERE id=?", (message_id,)).fetchone()
    if row is None or not row["target_chat_id"]:
        return False

    rendered = None
    # 各 DB 函数内部都会以最新行重渲染，最后一次写库的结果即最终文本。
    if add_tags:
        rendered = add_manual_tags(conn, message_id, add_tags)
    if remove_tag_names:
        rendered = remove_tags(conn, message_id, remove_tag_names)
    if rating is not None:
        rendered = update_rating(conn, message_id, rating)
    if rendered is None:
        return False

    await client.edit_message(
        row["target_chat_id"], row["target_message_id"], rendered
    )
    if indexer is not None:
        indexer.schedule()
    return True
