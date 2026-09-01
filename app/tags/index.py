"""Tag 统计与索引文本生成（Phase 9）。

统计以「归档副本」为单位：target_tags × message_targets 聚合，保证
多对多下每个频道的索引只算自己频道内的副本，且 Web 端的 target 级
Tag 编辑（只写 target_tags）能反映到计数里；Telegram 侧更新置顶索引
消息、保存条消息 id 与搜索链接的渲染在事件层完成。
"""

from __future__ import annotations

import sqlite3


def compute_tag_counts(
    conn: sqlite3.Connection,
    *,
    target_chat_id: int | None = None,
) -> list[tuple[str, int]]:
    """返回按使用次数降序的 (tag 名, 次数) 列表。

    以归档副本为统计单位：一条源消息归档到 N 个频道，其 Tag 在全局
    统计中计 N 次；target_chat_id 指定时只统计该频道内 status='archived'
    的副本（多对多场景每个频道有各自的索引）；缺省统计全部频道。
    """
    if target_chat_id is None:
        where = "WHERE mt.status = 'archived'"
        params: tuple[int, ...] = ()
    else:
        where = "WHERE mt.status = 'archived' AND mt.target_chat_id = ?"
        params = (target_chat_id,)
    rows = conn.execute(
        "SELECT t.name, COUNT(*) AS cnt "
        "FROM target_tags tt "
        "JOIN message_targets mt ON mt.id = tt.target_id "
        "JOIN tags t ON t.id = tt.tag_id "
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
