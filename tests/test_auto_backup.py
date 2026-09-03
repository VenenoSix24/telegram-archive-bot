"""定时自动备份：到期判断、备份产物、保留清理与 Telegram 上传容错。"""

from __future__ import annotations

import asyncio
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.backup_scheduler import AutoBackupScheduler
from app.config import (
    DEFAULT_BACKUP_INTERVAL_DAYS,
    Config,
    SourceChat,
    normalize_backup_interval,
)
from app.database.migrate import apply_migrations, open_db


class FakeClient:
    """记录 send_file 调用的假客户端；可注入异常模拟上传失败。"""

    def __init__(self, error: Exception | None = None) -> None:
        self.calls: list[tuple[int, Path, str]] = []
        self._error = error

    async def send_file(self, chat_id, path, caption=""):
        if self._error is not None:
            raise self._error
        self.calls.append((chat_id, Path(path), caption))


def make_config(tmp_path: Path, **overrides) -> Config:
    """临时数据库 + 最小 Config；override 可改 backup_* 字段。"""
    db_path = tmp_path / "archive.sqlite"
    conn = open_db(db_path)
    apply_migrations(conn)
    conn.close()
    values = {
        "api_id": 1,
        "api_hash": "hash",
        "bot_token": None,
        "source_chats": [SourceChat(chat_id=-1001, name="游戏")],
        "database_path": str(db_path),
        "config_path": str(tmp_path / "config.yaml"),
    }
    values.update(overrides)
    return Config(**values)


def make_scheduler(
    tmp_path: Path, client=None, *, check_interval: float = 3600.0, **overrides
) -> AutoBackupScheduler:
    return AutoBackupScheduler(
        client, make_config(tmp_path, **overrides), check_interval=check_interval
    )


def seed_backup(database_path: str, name: str, age_days: float) -> Path:
    """伪造一个带 mtime 的历史备份文件（不必是合法 SQLite）。"""
    path = Path(database_path).with_name(name)
    path.write_bytes(b"stub")
    stamp = (datetime.now(UTC) - timedelta(days=age_days)).timestamp()
    os.utime(path, (stamp, stamp))
    return path


def test_is_due_when_no_backup(tmp_path):
    scheduler = make_scheduler(tmp_path)
    assert scheduler.is_due() is True


def test_is_due_respects_interval(tmp_path):
    config = make_config(tmp_path, backup_interval_days=7)
    seed_backup(config.database_path, "archive.sqlite.20240101T000000Z.bak", age_days=2)
    scheduler = AutoBackupScheduler(None, config)
    assert scheduler.is_due() is False
    # 把 mtime 拨到 8 天前：超过 7 天间隔，判定到期
    old = (datetime.now(UTC) - timedelta(days=8)).timestamp()
    backup = next(Path(config.database_path).parent.glob("*.bak"))
    os.utime(backup, (old, old))
    assert scheduler.is_due() is True


async def test_run_once_creates_valid_backup(tmp_path):
    scheduler = make_scheduler(tmp_path)
    path = await scheduler.run_once()
    assert path is not None and path.exists()
    assert path.name.startswith("archive.sqlite.") and path.name.endswith(".bak")
    # 刚备份完不应立刻到期
    assert scheduler.is_due() is False


async def test_run_once_invalid_database_returns_none(tmp_path):
    config = make_config(tmp_path)
    # 备份前把库文件换成垃圾内容，模拟损坏的数据库
    Path(config.database_path).write_bytes(b"not a sqlite database at all")
    scheduler = AutoBackupScheduler(None, config)
    assert await scheduler.run_once() is None
    assert not list(tmp_path.glob("*.bak"))


async def test_upload_called_when_chat_id_set(tmp_path):
    client = FakeClient()
    scheduler = make_scheduler(tmp_path, client=client, backup_upload_chat_id=-1003)
    path = await scheduler.run_once()
    assert len(client.calls) == 1
    chat_id, uploaded, caption = client.calls[0]
    assert chat_id == -1003
    assert uploaded == path
    assert path.name in caption


async def test_upload_skipped_without_chat_id(tmp_path):
    client = FakeClient()
    scheduler = make_scheduler(tmp_path, client=client)
    await scheduler.run_once()
    assert client.calls == []


async def test_upload_failure_does_not_break_backup(tmp_path):
    client = FakeClient(error=RuntimeError("boom"))
    scheduler = make_scheduler(tmp_path, client=client, backup_upload_chat_id=-1003)
    path = await scheduler.run_once()
    assert path is not None and path.exists()


async def test_retention_keeps_newest(tmp_path):
    config = make_config(tmp_path, backup_retain=2)
    seed_backup(config.database_path, "archive.sqlite.20240101T000000Z.bak", age_days=30)
    seed_backup(config.database_path, "archive.sqlite.20240102T000000Z.bak", age_days=20)
    seed_backup(config.database_path, "archive.sqlite.20240103T000000Z.bak", age_days=10)
    new_path = await AutoBackupScheduler(None, config).run_once()
    remaining = sorted(Path(config.database_path).parent.glob("*.bak"))
    # 只保留最新 2 份：本次新备份 + 1 月 3 日那份；更旧的被清掉
    assert [p.name for p in remaining] == [
        "archive.sqlite.20240103T000000Z.bak",
        new_path.name,
    ]


def test_start_noop_when_disabled(tmp_path):
    scheduler = make_scheduler(tmp_path, backup_enabled=False)

    async def noop_run():
        raise AssertionError("disabled scheduler must not run")

    scheduler.run = noop_run  # type: ignore[method-assign]
    scheduler.start()
    assert scheduler._task is None


async def test_run_loop_backs_up_then_waits(tmp_path):
    # 用极短巡检周期模拟「启动即补跑 + 循环待命」
    scheduler = make_scheduler(tmp_path, check_interval=0.01)
    scheduler.start()
    try:
        for _ in range(100):
            if list(tmp_path.glob("*.bak")):
                break
            await asyncio.sleep(0.01)
        assert list(tmp_path.glob("*.bak"))
    finally:
        await scheduler.stop()
    assert scheduler._task is None


def test_normalize_backup_interval():
    for days in (1, 3, 7, 30):
        assert normalize_backup_interval(days) == days
    assert normalize_backup_interval(None) == DEFAULT_BACKUP_INTERVAL_DAYS
    assert normalize_backup_interval("5") == DEFAULT_BACKUP_INTERVAL_DAYS
    assert normalize_backup_interval(-1) == DEFAULT_BACKUP_INTERVAL_DAYS


def test_prune_ignores_missing_files(tmp_path, monkeypatch):
    scheduler = make_scheduler(tmp_path)
    ghost = tmp_path / "archive.sqlite.20240101T000000Z.bak"
    monkeypatch.setattr(
        scheduler, "_backup_paths", lambda: [ghost] * 2
    )  # 同一文件出现两次，unlink 一次后第二次应被容忍
    scheduler._prune_local()
    assert not ghost.exists()
