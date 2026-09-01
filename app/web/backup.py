"""受控的配置与 SQLite 备份、恢复、重置操作。"""

from __future__ import annotations

import shutil
import sqlite3
from datetime import UTC, datetime
from pathlib import Path


def _stamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


def backup_config(path: Path) -> Path:
    if not path.exists():
        raise FileNotFoundError(path)
    destination = path.with_name(f"{path.name}.{_stamp()}.bak")
    shutil.copy2(path, destination)
    return destination


def backup_database(path: Path) -> Path:
    if not path.exists():
        raise FileNotFoundError(path)
    destination = path.with_name(f"{path.name}.{_stamp()}.bak")
    source = sqlite3.connect(path)
    target = sqlite3.connect(destination)
    try:
        source.backup(target)
    finally:
        target.close()
        source.close()
    return destination


def reset_database(conn: sqlite3.Connection) -> None:
    tables = [
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name NOT LIKE 'sqlite_%' AND name <> 'schema_version'"
        )
    ]
    conn.execute("PRAGMA foreign_keys=OFF")
    try:
        for table in tables:
            conn.execute(f'DELETE FROM "{table.replace(chr(34), chr(34) * 2)}"')
    finally:
        conn.execute("PRAGMA foreign_keys=ON")
    conn.commit()
