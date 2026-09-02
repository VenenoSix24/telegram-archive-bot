"""查询层：Web 读取端点的数据库访问与素材展开/过滤/分页。

连接策略：每个请求开独立短连接、用完即关。sqlite3.Connection 的上下文
管理器只管事务提交/回滚、不会关闭连接——旧实现 `with _connect(...)` 因此
每请求泄漏一个连接对象，这里统一走 open_connection 显式 close。

列表/统计 SQL 集中在本模块，路由层只做编排；序列化见 app.web.serializers。
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path

from app.web.config_editor import read_editable_config
from app.web.serializers import apply_target_names, expand_target, serialize_message

_QUEUE_COUNTS = "SELECT status, COUNT(*) AS n FROM queue GROUP BY status"


@contextmanager
def open_connection(database_path: str):
    """打开一个请求级短连接，退出时确保 close（连接泄漏修复点）。"""
    conn = sqlite3.connect(database_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def sql_filters(query) -> tuple[str, list]:
    """构造仍可直接映射到 messages 表的筛选条件。"""
    conds: list[str] = []
    params: list[object] = []
    media_type = query.get("media_type")
    if media_type:
        conds.append("media_type = ?")
        params.append(media_type)
    where = f"WHERE {' AND '.join(conds)}" if conds else ""
    return where, params


def matches_message(message: dict, query, status: str = "all") -> bool:
    """Python 侧过滤：status/rating/target/q/多标签 AND。"""
    if status != "all":
        expected = "archived" if status == "active" else "deleted"
        if message["status"] != expected:
            return False
    rating = query.get("rating")
    if rating not in (None, "") and message["rating"] != int(rating):
        return False
    target = query.get("target_chat_id")
    if target and message["target_chat_id"] != int(target):
        return False
    text = query.get("q")
    searchable = f'{message["original_text"] or ""} {message["rendered_text"] or ""}'
    if text and text.lower() not in searchable.lower():
        return False
    # tag 可重复传多个（?tag=A&tag=B），交集过滤：同时带所有指定标签才命中
    tags = query.getlist("tag")
    if tags:
        names = {item["name"] for item in message["tags"]}
        if not all(tag in names for tag in tags):
            return False
    return True


def list_messages(
    conn: sqlite3.Connection,
    query,
    *,
    status: str = "active",
    limit: int = 30,
    offset: int = 0,
    target_names: dict[int, str] | None = None,
) -> dict:
    """列出素材：父表/副本展开 → 过滤 → 排序 → 切片。"""
    names = target_names or {}
    where, params = sql_filters(query)
    rows = conn.execute(
        f"SELECT * FROM messages {where} ORDER BY id DESC", params
    ).fetchall()
    expanded = []
    for row in rows:
        message = apply_target_names(serialize_message(conn, row), names)
        if not message["targets"] or message["targets"][0].get("id") is None:
            if matches_message(message, query, status):
                expanded.append(message)
            continue
        for target in message["targets"]:
            item = expand_target(message, target)
            if matches_message(item, query, status):
                expanded.append(item)
    expanded.sort(
        key=lambda item: (item["created_at"], item.get("target_id") or 0),
        reverse=True,
    )
    return {
        "items": expanded[offset:offset + limit],
        "total": len(expanded),
        "limit": limit,
        "offset": offset,
    }


def get_message_row(conn: sqlite3.Connection, message_id: int):
    return conn.execute("SELECT * FROM messages WHERE id=?", (message_id,)).fetchone()


def tag_counts(conn: sqlite3.Connection) -> dict:
    """标签清单 + 使用计数（含未使用的标签）。"""
    rows = conn.execute(
        "SELECT t.name, t.normalized_name, COUNT(mt.message_id) AS count "
        "FROM tags t LEFT JOIN message_tags mt ON mt.tag_id = t.id "
        "GROUP BY t.id ORDER BY count DESC, t.name"
    ).fetchall()
    return {
        "items": [
            {"name": r["name"], "count": r["count"]} for r in rows
        ],
        "total": len(rows),
    }


def stats_body(
    database_path: str,
    config_path: str | None = None,
    chat_names: dict[int, str] | None = None,
) -> dict:
    """概览统计：messages/tags/queue/targets/runtime（单连接一次取齐）。"""
    with open_connection(database_path) as conn:
        total = conn.execute("SELECT COUNT(*) AS n FROM messages").fetchone()["n"]
        archived = conn.execute(
            "SELECT COUNT(*) AS n FROM messages WHERE status='archived'"
        ).fetchone()["n"]
        sources = conn.execute(
            "SELECT COUNT(DISTINCT source_chat_id) AS n FROM messages"
        ).fetchone()["n"]
        by_type = {
            row["media_type"]: row["n"]
            for row in conn.execute(
                "SELECT media_type, COUNT(*) AS n FROM messages GROUP BY media_type"
            )
        }
        tag_rows = conn.execute(
            "SELECT COUNT(DISTINCT tag_id) AS n FROM message_tags"
        ).fetchone()["n"]
        tags = conn.execute("SELECT COUNT(*) AS n FROM tags").fetchone()["n"]
        has_target_table = True
        try:
            target_rows = conn.execute(
                "SELECT target_chat_id, COUNT(*) AS n FROM message_targets "
                "WHERE status='archived' GROUP BY target_chat_id ORDER BY n DESC"
            ).fetchall()
        except sqlite3.OperationalError as exc:
            if "no such table: message_targets" not in str(exc):
                raise
            has_target_table = False
            target_rows = conn.execute(
                "SELECT target_chat_id, COUNT(*) AS n FROM messages "
                "WHERE target_chat_id IS NOT NULL GROUP BY target_chat_id ORDER BY n DESC"
            ).fetchall()
        # 目标名与卡片同源：配置备注名 + 运行时解析的会话名，缺失回退前端拼 ID
        names: dict[int, str] = {}
        if config_path:
            try:
                editable = read_editable_config(Path(config_path))
                names = {
                    t["chat_id"]: t["name"]
                    for t in editable["target_channels"]
                    if t.get("chat_id") is not None
                }
            except (OSError, ValueError, TypeError):
                names = {}
        names.update(chat_names or {})
        targets = [
            {
                "chat_id": r["target_chat_id"],
                "count": r["n"],
                "name": names.get(r["target_chat_id"]) or "",
            }
            for r in target_rows
        ]
        queue = {"pending": 0, "processing": 0, "success": 0, "failed": 0}
        for row in conn.execute(_QUEUE_COUNTS):
            queue[row["status"]] = row["n"]
        return {
            "messages": {
                "total": total,
                "archived": archived,
                "sources": sources,
                "by_type": by_type,
            },
            "tags": {"total": tags, "with_messages": tag_rows},
            "queue": queue,
            "targets": targets,
            "runtime": {
                "database": Path(database_path).name,
                "latest_message_id": conn.execute(
                    "SELECT COALESCE(MAX(id), 0) AS n FROM messages"
                ).fetchone()["n"],
                "latest_target_id": conn.execute(
                    "SELECT COALESCE(MAX(id), 0) AS n FROM message_targets"
                ).fetchone()["n"] if has_target_table else 0,
            },
        }
