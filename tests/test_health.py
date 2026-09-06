"""/health 探活端点与后台任务失败持久化。"""

from __future__ import annotations

import sqlite3

from fastapi.testclient import TestClient

from app.config import Config
from app.database.migrate import apply_migrations, open_db
from app.task_failures import CAP, last_failure, recent_failures, record_failure
from app.web.app import create_app


def _config(database_path: str) -> Config:
    return Config(
        api_id=1,
        api_hash="h",
        bot_token=None,
        source_chats=[],
        target_channel_id=-100,
        forward_interval=3.0,
        retry_count=3,
        show_link=True,
        preserve_original=True,
        rating_enabled=True,
        admins=frozenset({1}),
        database_path=database_path,
        config_path=None,
        web_enabled=True,
        web_host="127.0.0.1",
        web_port=8000,
        web_token="secret-token",
    )


# ---- /health ----


def test_health_ok_payload(tmp_path):
    db = tmp_path / "archive.sqlite"
    conn = open_db(db)
    apply_migrations(conn)
    conn.close()
    with TestClient(create_app(_config(str(db)))) as client:
        resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["database"] == {"reachable": True, "user_version": 8}
    assert body["last_failure"] is None
    assert isinstance(body["uptime_seconds"], (int, float))
    assert body["uptime_seconds"] >= 0
    assert isinstance(body["version"], str)


def test_health_does_not_leak_paths_or_config(tmp_path):
    db = tmp_path / "archive.sqlite"
    open_db(db).close()
    with TestClient(create_app(_config(str(db)))) as client:
        body = client.get("/health").json()
    resp_text = str(body)
    assert str(tmp_path) not in resp_text
    assert "secret-token" not in resp_text


def test_health_reports_last_failure(tmp_path):
    db = tmp_path / "archive.sqlite"
    open_db(db).close()
    record_failure(db, "auto_backup", "disk full")
    with TestClient(create_app(_config(str(db)))) as client:
        body = client.get("/health").json()
    assert body["last_failure"]["task"] == "auto_backup"
    assert body["last_failure"]["error"] == "disk full"


# ---- 失败持久化 ----


def test_record_failure_and_last(tmp_path):
    db = tmp_path / "t.sqlite"
    record_failure(db, "a", "boom")
    record_failure(db, "b", "bang")
    assert last_failure(db)["task"] == "b"
    tasks = [item["task"] for item in recent_failures(db)]
    assert tasks == ["b", "a"]


def test_record_failure_prunes_to_cap(tmp_path):
    db = tmp_path / "t.sqlite"
    for i in range(CAP + 20):
        record_failure(db, "task", f"error {i}")
    conn = sqlite3.connect(str(db))
    count = conn.execute("SELECT COUNT(*) FROM task_failures").fetchone()[0]
    newest = conn.execute("SELECT error FROM task_failures ORDER BY id DESC LIMIT 1")
    assert count == CAP
    assert newest.fetchone()[0] == f"error {CAP + 19}"
    conn.close()


def test_record_failure_never_raises(tmp_path):
    # 库文件是目录，打开必然 sqlite3.Error；调用方不能被拖垮
    bad = tmp_path / "dir.sqlite"
    bad.mkdir()
    record_failure(bad, "task", "x")
    assert recent_failures(bad) == []
    assert last_failure(bad) is None


def test_backup_scheduler_records_failure(tmp_path, monkeypatch):
    import app.backup_scheduler as bs

    db = tmp_path / "t.sqlite"
    open_db(db).close()

    def _boom(_path):
        raise RuntimeError("no space left")

    monkeypatch.setattr(bs, "backup_database", _boom)
    cfg = Config(
        api_id=1,
        api_hash="h",
        bot_token=None,
        source_chats=[],
        target_channel_id=-100,
        forward_interval=3.0,
        retry_count=3,
        show_link=True,
        preserve_original=True,
        rating_enabled=True,
        admins=frozenset({1}),
        database_path=str(db),
        config_path=None,
        backup_enabled=True,
        backup_interval_days=1,
        backup_retain=3,
        backup_upload_chat_id=None,
    )
    scheduler = bs.AutoBackupScheduler(client=None, config=cfg)

    import asyncio

    assert asyncio.run(scheduler.run_once()) is None
    assert last_failure(db)["task"] == "auto_backup"
    assert "no space left" in last_failure(db)["error"]
