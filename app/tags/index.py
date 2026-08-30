"""Tag 统计与索引文本生成（Phase 9）。

统计直接对 message_tags 聚合，保证计数与 DB 一致；Telegram 侧更新
置顶索引消息、保存条消息 id 与搜索链接的渲染在事件层完成。
"""

from __future__ import annotations

import sqlite3


def compute_tag_counts(
    conn: sqlite3.Connection,
    *,
    target_chat_id: int | None = None,
) -> list[tuple[str, int]]:
    """返回按使用次数降序的 (tag 名, 消息数) 列表。

    target_chat_id 指定时只统计归档到该目标频道的消息（多对多场景每个
    频道有各自的索引）；缺省统计全部。
    """
    where = "" if target_chat_id is None else "WHERE m.target_chat_id = ?"
    params: tuple[int, ...] = () if target_chat_id is None else (target_chat_id,)
    rows = conn.execute(
        "SELECT t.name, COUNT(mt.message_id) AS cnt "
        "FROM message_tags mt "
        "JOIN messages m ON m.id = mt.message_id "
        "JOIN tags t ON t.id = mt.tag_id "
        f"{where} "
        "GROUP BY t.id ORDER BY cnt DESC, t.name",
        params,
    ).fetchall()
    return [(row["name"], row["cnt"]) for row in rows]


def format_tag_index(counts: list[tuple[str, int]]) -> str:
    """生成置顶索引消息文本：📚 Tags + 每行 #tag · count。"""
    lines = ["📚 Tags", ""]
    if not counts:
        lines.append("（暂无 Tag）")
        return "\n".join(lines)
    lines.extend(f"#{name} · {count}" for name, count in counts)
    return "\n".join(lines)
