"""后台任务失败持久化：task_failures 表的小型读写封装。

备份/上传/索引等常驻任务失败时落一条记录（只记 task 名 + 错误文本），
供 /health 展示最近一次失败。写入自动裁剪到上限，防止表无限增长。
"""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

from app.database.migrate import open_db

logger = logging.getLogger(__name__)

# 保留最近 N 条，超出按 id 从旧到新删除
CAP = 100

# /health 展示用的错误文本上限，避免极端堆栈撑爆响应
_ERROR_MAX_CHARS = 500


def record_failure(database_path: str | Path, task: str, error: str, cap: int = CAP) -> None:
    """记录一次任务失败并裁剪到 cap 条。失败记录本身绝不能拖垮调用方。"""
    message = (error or "").strip() or "unknown error"
    try:
        conn = open_db(database_path)
        try:
            # 表缺失（未迁移/旧库）时兜底建表，失败记录不依赖迁移时序
            conn.execute(
                "CREATE TABLE IF NOT EXISTS task_failures ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT,"
                "task TEXT NOT NULL,"
                "error TEXT NOT NULL,"
                "created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)"
            )
            conn.execute(
                "INSERT INTO task_failures (task, error) VALUES (?, ?)", (task, message)
            )
            conn.execute(
                "DELETE FROM task_failures WHERE id NOT IN ("
                "SELECT id FROM task_failures ORDER BY id DESC LIMIT ?)", (cap,)
            )
            conn.commit()
        finally:
            conn.close()
    except sqlite3.Error:
        logger.exception("failed to persist task failure for %s", task)


def recent_failures(database_path: str | Path, limit: int = 10) -> list[dict]:
    """最近的失败记录，新的在前；出错或无表时返回空列表。"""
    try:
        conn = open_db(database_path)
        try:
            rows = conn.execute(
                "SELECT task, error, created_at FROM task_failures "
                "ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        finally:
            conn.close()
    except sqlite3.Error:
        logger.exception("failed to read task failures")
        return []
    return [
        {"task": row["task"], "error": row["error"], "created_at": row["created_at"]}
        for row in rows
    ]


def last_failure(database_path: str | Path) -> dict | None:
    """最近一次失败，无记录返回 None。"""
    failures = recent_failures(database_path, limit=1)
    return failures[0] if failures else None
