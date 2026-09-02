"""Web API 响应序列化：DB 行 → 前端契约 JSON。

结构契约（前端零改动依赖）：message/material 字段名、material_id 前缀
（message:/target:）、targets 列表与伪目标（旧数据无副本行时回退父级）。
"""

from __future__ import annotations

import sqlite3


def serialize_message(conn: sqlite3.Connection, row) -> dict:
    """把 messages 行序列化成消息 dict（含 tags 与全部目标副本）。"""
    tags = [
        {"name": t["name"], "type": t["type"]}
        for t in conn.execute(
            "SELECT t.name, mt.type FROM message_tags mt "
            "JOIN tags t ON t.id = mt.tag_id "
            "WHERE mt.message_id = ? ORDER BY mt.type, t.name",
            (row["id"],),
        )
    ]
    keys = row.keys()
    original_html = row["original_html"] if "original_html" in keys else ""
    try:
        target_rows = conn.execute(
            "SELECT id, target_chat_id, target_message_id, target_url, status, "
            "original_text, original_html, rendered_text, rating "
            "FROM message_targets WHERE message_id=? ORDER BY id",
            (row["id"],),
        )
    except sqlite3.OperationalError as exc:
        if "no such table: message_targets" not in str(exc):
            raise
        target_rows = []
    targets = []
    for target in target_rows:
        try:
            target_tag_rows = conn.execute(
                "SELECT t.name, tt.type FROM target_tags tt JOIN tags t ON t.id=tt.tag_id "
                "WHERE tt.target_id=? ORDER BY tt.type, t.name",
                (target["id"],),
            )
        except sqlite3.OperationalError as exc:
            if "no such table: target_tags" not in str(exc):
                raise
            target_tag_rows = []
        target_tags = [{"name": tag["name"], "type": tag["type"]} for tag in target_tag_rows]
        targets.append(_target_dict(target, target_tags))
    if not targets and row["target_chat_id"] is not None:
        targets = [{
            "id": None,
            "chat_id": row["target_chat_id"],
            "message_id": row["target_message_id"],
            "url": row["target_url"],
            "status": row["status"],
        }]
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
        "targets": targets,
        "file_name": row["file_name"],
        "file_size": row["file_size"],
        "duration": row["duration"],
        "status": row["status"],
        "created_at": row["created_at"],
        "tags": tags,
        "thumb": {"available": bool(row["thumb_path"]), "path": row["thumb_path"]},
    }


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
