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

from fastapi import HTTPException

from app.web.config_editor import read_editable_config
from app.web.serializers import serialize_materials

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



def _material_filters(query, status: str, joined: bool) -> tuple[str, list]:
    """素材列表的 WHERE 条件；joined=True 时条件取 COALESCE(副本, 父表)。

    与旧版 Python 侧过滤语义一致：status 映射 archived/deleted、rating 与
    target_chat_id 精确匹配、q 对正文+渲染文本做大小写不敏感子串匹配、
    tag 可多值（?tag=A&tag=B）AND 交集——副本素材看副本标签，父表素材看父表标签。
    """
    conds: list[str] = []
    params: list[object] = []
    media_type = query.get("media_type")
    if media_type:
        conds.append("m.media_type = ?")
        params.append(media_type)
    if status != "all":
        conds.append(f"{_coalesce('status', joined)} = ?")
        params.append("archived" if status == "active" else "deleted")
    rating = query.get("rating")
    if rating not in (None, ""):
        try:
            value = int(rating)
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail="invalid rating") from exc
        conds.append(f"{_coalesce('rating', joined)} = ?")
        params.append(value)
    target = query.get("target_chat_id")
    if target:
        try:
            value = int(target)
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail="invalid target_chat_id") from exc
        conds.append(f"{_coalesce('target_chat_id', joined)} = ?")
        params.append(value)
    text = query.get("q")
    if text:
        searchable = (
            "COALESCE(mt.original_text, '') || ' ' || COALESCE(mt.rendered_text, '')"
            if joined
            else "COALESCE(m.original_text, '') || ' ' || COALESCE(m.rendered_text, '')"
        )
        escaped = text.replace("\\", "\\\\").replace("%", r"\%").replace("_", r"\_")
        conds.append(f"{searchable} LIKE ? ESCAPE '\\'")
        params.append(f"%{escaped}%")
    for tag in query.getlist("tag"):
        if joined:
            conds.append(
                "(EXISTS (SELECT 1 FROM target_tags tt JOIN tags t ON t.id = tt.tag_id "
                "WHERE tt.target_id = mt.id AND t.name = ?) "
                "OR (mt.id IS NULL AND EXISTS (SELECT 1 FROM message_tags mt2 "
                "JOIN tags t2 ON t2.id = mt2.tag_id "
                "WHERE mt2.message_id = m.id AND t2.name = ?)))"
            )
            params.extend([tag, tag])
        else:
            conds.append(
                "EXISTS (SELECT 1 FROM message_tags mt2 JOIN tags t ON t.id = mt2.tag_id "
                "WHERE mt2.message_id = m.id AND t.name = ?)"
            )
            params.append(tag)
    where = f"WHERE {' AND '.join(conds)}" if conds else ""
    return where, params


def _coalesce(column: str, joined: bool) -> str:
    return f"COALESCE(mt.{column}, m.{column})" if joined else f"m.{column}"


_JOINED_COLUMNS = (
    "m.*, "
    "mt.id AS mt_id, mt.target_chat_id AS mt_chat_id, "
    "mt.target_message_id AS mt_message_id, mt.target_url AS mt_url, "
    "mt.status AS mt_status, mt.original_text AS mt_original_text, "
    "mt.original_html AS mt_original_html, mt.rendered_text AS mt_rendered_text, "
    "mt.rating AS mt_rating"
)

_FALLBACK_COLUMNS = (
    "m.*, "
    "NULL AS mt_id, NULL AS mt_chat_id, NULL AS mt_message_id, NULL AS mt_url, "
    "NULL AS mt_status, NULL AS mt_original_text, NULL AS mt_original_html, "
    "NULL AS mt_rendered_text, NULL AS mt_rating"
)

_JOINED_FROM = "FROM messages m LEFT JOIN message_targets mt ON mt.message_id = m.id"
_FALLBACK_FROM = "FROM messages m"


def list_messages(
    conn: sqlite3.Connection,
    query,
    *,
    status: str = "active",
    limit: int = 30,
    offset: int = 0,
    target_names: dict[int, str] | None = None,
) -> dict:
    """列出素材：SQL 侧展开父表/副本、过滤、排序，LIMIT/OFFSET 真分页。

    messages LEFT JOIN message_targets 正好是素材展开语义：有 N 条副本出
    N 行，无副本出 1 行父表素材。过滤与计数都在库内完成，序列化只处理
    当前页（旧实现全表拉到 Python 过滤 + 内存切片 + 逐行打库取标签）。
    message_targets 表不存在（旧库/最小测试库）时退化为纯父表查询。
    """
    limit = max(0, limit)
    offset = max(0, offset)
    try:
        total, rows = _query_materials(conn, query, status, limit, offset, joined=True)
    except sqlite3.OperationalError as exc:
        if "no such table: message_targets" not in str(exc):
            raise
        total, rows = _query_materials(conn, query, status, limit, offset, joined=False)
    items = serialize_materials(conn, rows, target_names or {})
    return {"items": items, "total": total, "limit": limit, "offset": offset}


def _query_materials(conn, query, status, limit, offset, *, joined: bool):
    """同一 WHERE 下先 COUNT 再取页；返回 (total, 当前行)。"""
    where, params = _material_filters(query, status, joined)
    columns = _JOINED_COLUMNS if joined else _FALLBACK_COLUMNS
    source = _JOINED_FROM if joined else _FALLBACK_FROM
    order = (
        "ORDER BY m.created_at DESC, COALESCE(mt.id, 0) DESC"
        if joined
        else "ORDER BY m.created_at DESC"
    )
    total = conn.execute(
        f"SELECT COUNT(*) AS n {source} {where}", params
    ).fetchone()["n"]
    rows = conn.execute(
        f"SELECT {columns} {source} {where} {order} LIMIT ? OFFSET ?",
        [*params, limit, offset],
    ).fetchall()
    return total, rows


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
