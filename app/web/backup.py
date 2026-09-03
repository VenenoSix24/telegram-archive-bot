"""受控的配置与 SQLite 备份、恢复、重置操作。"""

from __future__ import annotations

import os
import shutil
import sqlite3
import tempfile
from datetime import UTC, datetime
from pathlib import Path

_MAX_IMPORT_BYTES = 100 * 1024 * 1024


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
    except Exception:
        # 备份中途失败时清掉半成品，避免 0 字节 .bak 混进 Web 备份列表
        destination.unlink(missing_ok=True)
        raise
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
    cache_dir = path.parent / "thumbs"
    if cache_dir.is_dir():
        for cached in cache_dir.iterdir():
            if cached.is_file():
                cached.unlink()


def backup_metadata(path: Path, kind: str) -> dict:
    stat = path.stat()
    return {
        "name": path.name,
        "kind": kind,
        "size": stat.st_size,
        "created_at": datetime.fromtimestamp(stat.st_mtime, UTC).isoformat(),
    }


def validate_config_backup(path: Path) -> None:
    from app.web.config_editor import read_editable_config

    read_editable_config(path)


def validate_database_backup(path: Path) -> None:
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        if conn.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ValueError("SQLite integrity check failed")
        tables = {
            row[0]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        if "messages" not in tables or "schema_version" not in tables:
            raise ValueError("not an archive database backup")
    finally:
        conn.close()


async def import_backup(chunks, destination: Path, kind: str) -> None:
    """Validate a streamed upload then atomically replace the managed file."""
    if kind not in {"config", "database"}:
        raise ValueError("invalid backup kind")
    with tempfile.NamedTemporaryFile(dir=destination.parent, delete=False) as temp:
        temporary = Path(temp.name)
        copied = 0
        async for chunk in chunks:
            copied += len(chunk)
            if copied > _MAX_IMPORT_BYTES:
                temporary.unlink(missing_ok=True)
                raise ValueError("backup file exceeds 100 MB")
            temp.write(chunk)
    try:
        if kind == "config":
            validate_config_backup(temporary)
            backup_config(destination)
        else:
            validate_database_backup(temporary)
            backup_database(destination)
        os.replace(temporary, destination)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
