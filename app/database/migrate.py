"""SQLite 连接与迁移执行。

V1 单进程 asyncio：所有数据库访问都在同一线程，sqlite3 同步接口足够，
不做连接池。WAL 缓解读写并发。
"""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

logger = logging.getLogger(__name__)

MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "migrations"


def open_db(path: str | Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def apply_migrations(
    conn: sqlite3.Connection, migrations_dir: Path = MIGRATIONS_DIR
) -> list[str]:
    """按文件名顺序应用未执行的迁移，返回本次新应用的版本列表。幂等可重放。"""
    conn.execute(
        "CREATE TABLE IF NOT EXISTS schema_version ("
        "version TEXT PRIMARY KEY, applied_at TEXT DEFAULT CURRENT_TIMESTAMP)"
    )
    applied = {row[0] for row in conn.execute("SELECT version FROM schema_version")}
    newly_applied: list[str] = []
    for file in sorted(migrations_dir.glob("*.sql")):
        if file.stem in applied:
            continue
        conn.executescript(file.read_text(encoding="utf-8"))
        conn.execute("INSERT INTO schema_version (version) VALUES (?)", (file.stem,))
        newly_applied.append(file.stem)
        logger.info("applied migration %s", file.stem)
    conn.commit()
    return newly_applied
