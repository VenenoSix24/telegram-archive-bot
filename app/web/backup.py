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


def reset_database(path: Path) -> None:
    """Clear application data using a connection owned by the request thread.

    The Telegram worker keeps its own connection on the event-loop thread. This
    short-lived connection avoids crossing SQLite's thread boundary; callers
    must restart the process before continuing archive work.
    """
    conn = sqlite3.connect(path)
    try:
        conn.execute("PRAGMA foreign_keys=ON")
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
                escaped = table.replace('"', '""')
                conn.execute(f'DELETE FROM "{escaped}"')
        finally:
            conn.execute("PRAGMA foreign_keys=ON")
        conn.commit()
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    finally:
        conn.close()
