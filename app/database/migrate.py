"""SQLite 连接与迁移执行。

V1 单进程 asyncio：所有数据库访问都在同一线程，sqlite3 同步接口足够，
不做连接池。WAL 缓解读写并发。

迁移状态双轨制：
- 老机制：migrations/*.sql 按文件名顺序执行，记录在 schema_version 表；
- 新机制：PRAGMA user_version 记录已到的编号（0001_*.sql → 1，以此类推）。
首次升级时旧库 user_version=0 但 schema_version 已有记录，此时不重放 DDL，
直接把 user_version 对齐到已应用的最大编号（基线 reconciliation）；之后
新迁移按 user_version 判断，schema_version 继续同步写入以保持备份校验等
既有逻辑兼容。
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


def _version_num(stem: str) -> int:
    """迁移编号取文件名前缀：0008_task_failures → 8。"""
    prefix = stem.split("_", 1)[0]
    return int(prefix) if prefix.isdigit() else 0


def _has_schema_version_table(conn: sqlite3.Connection) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='schema_version'"
    ).fetchone()
    return row is not None


def _ensure_schema_version_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        "CREATE TABLE IF NOT EXISTS schema_version ("
        "version TEXT PRIMARY KEY, applied_at TEXT DEFAULT CURRENT_TIMESTAMP)"
    )


def _adopt_user_version(conn: sqlite3.Connection) -> int:
    """旧库升级基线：schema_version 已有记录但 user_version=0。

    不重放任何 DDL，仅把 user_version 对齐到已应用迁移的最大编号，
    返回对齐后的版本号。
    """
    rows = conn.execute("SELECT version FROM schema_version").fetchall()
    baseline = max((_version_num(row[0]) for row in rows), default=0)
    conn.execute(f"PRAGMA user_version = {int(baseline)}")
    logger.info("adopted user_version=%s from schema_version table", baseline)
    return baseline


def apply_migrations(
    conn: sqlite3.Connection, migrations_dir: Path = MIGRATIONS_DIR
) -> list[str]:
    """按文件名顺序应用未执行的迁移，返回本次新应用的版本列表。幂等可重放。

    每个迁移单独提交并推进 user_version，中途失败时已完成的步骤不会重跑。
    """
    files = sorted(migrations_dir.glob("*.sql"))
    current = conn.execute("PRAGMA user_version").fetchone()[0]
    applied: set[str] = set()
    if _has_schema_version_table(conn):
        applied = {row[0] for row in conn.execute("SELECT version FROM schema_version")}
    else:
        _ensure_schema_version_table(conn)

    if current == 0 and applied:
        # 旧库已用 schema_version 管理迁移，首次升级只对齐 user_version，
        # 不重放 DDL（迁移 SQL 全部 IF NOT EXISTS，重放也无害，但没必要）。
        current = _adopt_user_version(conn)

    newly_applied: list[str] = []
    for file in files:
        num = _version_num(file.stem)
        if file.stem in applied or num <= current:
            continue
        conn.executescript(file.read_text(encoding="utf-8"))
        conn.execute("INSERT INTO schema_version (version) VALUES (?)", (file.stem,))
        conn.execute(f"PRAGMA user_version = {num}")
        conn.commit()
        current = num
        newly_applied.append(file.stem)
        logger.info("applied migration %s (user_version=%s)", file.stem, num)
    return newly_applied
