"""Web API 响应序列化：DB 行 → 前端契约 JSON。

结构契约（前端零改动依赖）：message/material 字段名、material_id 前缀
（message:/target:）、targets 列表与伪目标（旧数据无副本行时回退父级）。
"""

from __future__ import annotations

import sqlite3


def message_tags_by_id(conn: sqlite3.Connection, message_ids) -> dict[int, list[dict]]:
    """批量取消息标签：{message_id: [{name, type}, ...]}（单查询，修 N+1）。"""
    ids = sorted(set(message_ids))
    if not ids:
        return {}
    placeholders = ", ".join("?" * len(ids))
    rows = conn.execute(
        "SELECT mt.message_id, t.name, mt.type FROM message_tags mt "
        "JOIN tags t ON t.id = mt.tag_id "
        f"WHERE mt.message_id IN ({placeholders}) ORDER BY mt.type, t.name",
        ids,
    ).fetchall()
    grouped: dict[int, list[dict]] = {}
    for row in rows:
        grouped.setdefault(row["message_id"], []).append(
            {"name": row["name"], "type": row["type"]}
        )
    return grouped


def target_tags_by_id(conn: sqlite3.Connection, target_ids) -> dict[int, list[dict]]:
    """批量取副本标签：{target_id: [{name, type}, ...]}；无 target_tags 表返回空。"""
    ids = sorted(set(target_ids))
    if not ids:
        return {}
    try:
        placeholders = ", ".join("?" * len(ids))
        rows = conn.execute(
            "SELECT tt.target_id, t.name, tt.type FROM target_tags tt "
            "JOIN tags t ON t.id = tt.tag_id "
            f"WHERE tt.target_id IN ({placeholders}) ORDER BY tt.type, t.name",
            ids,
        ).fetchall()
    except sqlite3.OperationalError as exc:
        if "no such table: target_tags" not in str(exc):
            raise
        return {}
    grouped: dict[int, list[dict]] = {}
    for row in rows:
        grouped.setdefault(row["target_id"], []).append(
            {"name": row["name"], "type": row["type"]}
        )
    return grouped


def base_message_dict(row, tags: list[dict]) -> dict:
    """messages 行 → 消息 dict 骨架（targets 待填）。"""
    original_html = row["original_html"] if "original_html" in row.keys() else ""
    return {
        "id": row["id"],
        "material_id": f"message:{row['id']}",
        "source_chat_id": row["source_chat_id"],
        "source_message_id": row["source_message_id"],
        "target_chat_id": row["target_chat_id"],
        "target_message_id": row["target_message_id"],
        "media_type": row["media_type"],
        "media_group_id": row["media_group_id"],
        "original_text": row["original_text"],
        "original_html": original_html,
        "rendered_text": row["rendered_text"],
        "rating": row["rating"],
        "source_url": row["source_url"],
        "target_url": row["target_url"],
        "targets": [],
        "file_name": row["file_name"],
        "file_size": row["file_size"],
        "duration": row["duration"],
        "status": row["status"],
        "created_at": row["created_at"],
        "tags": tags,
        "thumb": {"available": bool(row["thumb_path"]), "path": row["thumb_path"]},
    }


def _pseudo_target(row) -> dict:
    """旧数据无副本行时的父级伪目标（无 id，仅供前端展示归属）。"""
    return {
        "id": None,
        "chat_id": row["target_chat_id"],
        "message_id": row["target_message_id"],
        "url": row["target_url"],
        "status": row["status"],
    }


def serialize_message(conn: sqlite3.Connection, row) -> dict:
    """把 messages 行序列化成消息 dict（含 tags 与全部目标副本）。"""
    message = base_message_dict(row, message_tags_by_id(conn, [row["id"]]).get(row["id"], []))
    try:
        target_rows = conn.execute(
            "SELECT id, target_chat_id, target_message_id, target_url, status, "
            "original_text, original_html, rendered_text, rating "
            "FROM message_targets WHERE message_id=? ORDER BY id",
            (row["id"],),
        ).fetchall()
    except sqlite3.OperationalError as exc:
        if "no such table: message_targets" not in str(exc):
            raise
        target_rows = []
    target_tags = target_tags_by_id(conn, [t["id"] for t in target_rows])
    message["targets"] = [
        _target_dict(target, target_tags.get(target["id"], [])) for target in target_rows
    ]
    if not message["targets"] and row["target_chat_id"] is not None:
        message["targets"] = [_pseudo_target(row)]
    return message


def serialize_materials(
    conn: sqlite3.Connection, rows, target_names: dict[int, str]
) -> list[dict]:
    """列表页专用：连接查询行 → 素材项（父表项或单副本展开项）。

    输入行由 queries.query_materials 产出：m.* 加 mt_* 别名列；
    标签按页批量取（每页 2 条查询，不再逐行打库）。
    """
    msg_tags = message_tags_by_id(conn, [row["id"] for row in rows])
    tgt_tags = target_tags_by_id(conn, [row["mt_id"] for row in rows if row["mt_id"] is not None])
    items = []
    for row in rows:
        message = base_message_dict(row, msg_tags.get(row["id"], []))
        if row["mt_id"] is None:
            # 无副本行：父表素材；旧数据回退伪目标
            if message["target_chat_id"] is not None:
                pseudo = _pseudo_target(row)
                pseudo["name"] = target_names.get(pseudo["chat_id"], "")
                message["targets"] = [pseudo]
            items.append(message)
            continue
        target = {
            "id": row["mt_id"],
            "chat_id": row["mt_chat_id"],
            "message_id": row["mt_message_id"],
            "url": row["mt_url"],
            "status": row["mt_status"],
            "original_text": row["mt_original_text"],
            "original_html": row["mt_original_html"],
            "rendered_text": row["mt_rendered_text"],
            "rating": row["mt_rating"],
            "tags": tgt_tags.get(row["mt_id"], []),
            "name": target_names.get(row["mt_chat_id"], ""),
        }
        items.append(expand_target(message, target))
    return items


def _target_dict(target, target_tags: list[dict]) -> dict:
    return {
        "id": target["id"],
        "chat_id": target["target_chat_id"],
        "message_id": target["target_message_id"],
        "url": target["target_url"],
        "status": target["status"],
        "original_text": target["original_text"],
        "original_html": target["original_html"],
        "rendered_text": target["rendered_text"],
        "rating": target["rating"],
        "tags": target_tags,
    }


def apply_target_names(message: dict, target_names: dict[int, str]) -> dict:
    """给消息的每个目标副本补人读名；缺失回空串（前端自行拼 ID）。"""
    for target in message["targets"]:
        target["name"] = target_names.get(target["chat_id"], "")
    return message


def expand_target(message: dict, target: dict) -> dict:
    """把消息 dict 展开成单副本素材项（material_id 换成 target: 前缀）。"""
    return {
        **message,
        "id": message["id"],
        "material_id": f"target:{target['id']}",
        "target_id": target["id"],
        "target_chat_id": target["chat_id"],
        "target_message_id": target["message_id"],
        "target_url": target["url"],
        "status": target["status"],
        "original_text": target["original_text"],
        "original_html": target["original_html"],
        "rendered_text": target["rendered_text"],
        "rating": target["rating"],
        "tags": target["tags"],
        "targets": [target],
    }
