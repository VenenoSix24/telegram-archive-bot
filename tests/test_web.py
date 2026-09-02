"""Web API：鉴权 + stats 读取端点。"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Config
from app.web.app import create_app


def _config(**overrides) -> Config:
    defaults = dict(
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
        url_template=None,
        database_path=":memory:",
        config_path=None,
        web_enabled=True,
        web_host="127.0.0.1",
        web_port=8000,
        web_token="secret-token",
    )
    defaults.update(overrides)
    return Config(**defaults)


@pytest.fixture
def seeded_db(tmp_path):
    """建一个带数据的内存库文件，供 stats 统计。"""
    path = tmp_path / "archive.sqlite"
    conn = sqlite3.connect(str(path))
    conn.executescript(
        """
        CREATE TABLE messages (
            id INTEGER PRIMARY KEY,
            source_chat_id INTEGER NOT NULL,
            source_message_id INTEGER NOT NULL,
            media_type TEXT NOT NULL DEFAULT 'text',
            status TEXT NOT NULL DEFAULT 'processed',
            target_chat_id INTEGER
        );
        CREATE TABLE tags (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL
        );
        CREATE TABLE message_tags (
            message_id INTEGER NOT NULL,
            tag_id INTEGER NOT NULL
        );
        CREATE TABLE queue (
            id INTEGER PRIMARY KEY,
            status TEXT NOT NULL DEFAULT 'pending'
        );
        INSERT INTO messages (id, source_chat_id, source_message_id, media_type,
            status, target_chat_id)
        VALUES (1, -1001, 1, 'photo', 'archived', -1005),
               (2, -1001, 2, 'video', 'archived', -1005),
               (3, -1002, 1, 'text', 'archived', -1006),
               (4, -1002, 2, 'text', 'processed', NULL);
        INSERT INTO tags (id, name) VALUES (1, '游戏'), (2, '软件');
        INSERT INTO message_tags (message_id, tag_id) VALUES (1, 1), (2, 1), (3, 2);
        INSERT INTO queue (id, status) VALUES (1, 'success'), (2, 'pending'), (3, 'failed');
        """
    )
    conn.commit()
    conn.close()
    return str(path)


def _client(tmp_path, token="secret-token"):
    db = tmp_path / "web.sqlite"
    sqlite3.connect(str(db)).close()
    cfg = _config(database_path=str(db), web_token=token)
    return TestClient(create_app(cfg))


def test_stats_requires_login(tmp_path, seeded_db):
    cfg = _config(database_path=seeded_db, web_token="secret-token")
    with TestClient(create_app(cfg)) as client:
        assert client.get("/api/v1/stats").status_code == 401


def test_login_rejects_wrong_token(tmp_path):
    with _client(tmp_path) as client:
        resp = client.post("/api/v1/auth/login", json={"token": "wrong"})
        assert resp.status_code == 401


def test_login_ok_and_stats(tmp_path, seeded_db):
    cfg = _config(database_path=seeded_db, web_token="secret-token")
    with TestClient(create_app(cfg)) as client:
        resp = client.post("/api/v1/auth/login", json={"token": "secret-token"})
        assert resp.status_code == 200
        assert resp.json() == {"ok": True}

        stats = client.get("/api/v1/stats")
        assert stats.status_code == 200
        body = stats.json()
        assert body["messages"]["total"] == 4
        assert body["messages"]["archived"] == 3
        assert body["messages"]["sources"] == 2
        assert body["messages"]["by_type"] == {"photo": 1, "video": 1, "text": 2}
        assert body["tags"] == {"total": 2, "with_messages": 2}
        assert body["queue"] == {"pending": 1, "processing": 0, "success": 1, "failed": 1}
        assert body["targets"] == [{"chat_id": -1005, "count": 2}, {"chat_id": -1006, "count": 1}]


def test_logout_invalidates_session(tmp_path):
    with _client(tmp_path) as client:
        client.post("/api/v1/auth/login", json={"token": "secret-token"})
        assert client.post("/api/v1/auth/logout").status_code == 200
        assert client.get("/api/v1/stats").status_code == 401


def test_health_requires_login(tmp_path):
    with _client(tmp_path) as client:
        assert client.get("/api/v1/health").status_code == 401


def _logged_client(db_path, token="secret-token"):
    cfg = _config(database_path=db_path, web_token=token)
    client = TestClient(create_app(cfg))
    client.post("/api/v1/auth/login", json={"token": token})
    return client


def _make_schema_db(tmp_path, name="schema.sqlite") -> str:
    """建一个带真实 Web 所需表结构（messages/tags/message_tags）的库文件。"""
    import sqlite3

    db = tmp_path / name
    raw = sqlite3.connect(str(db))
    raw.row_factory = sqlite3.Row
    raw.executescript(
        """
        CREATE TABLE messages (
            id INTEGER PRIMARY KEY,
            source_chat_id INTEGER NOT NULL,
            source_message_id INTEGER NOT NULL,
            target_chat_id INTEGER,
            target_message_id INTEGER,
            media_group_id TEXT,
            media_type TEXT NOT NULL DEFAULT 'text',
            original_text TEXT NOT NULL DEFAULT '',
            rendered_text TEXT NOT NULL DEFAULT '',
            source_url TEXT,
            target_url TEXT,
            rating INTEGER NOT NULL DEFAULT 0,
            thumb_path TEXT,
            file_name TEXT NOT NULL DEFAULT '',
            file_size INTEGER,
            duration INTEGER,
            status TEXT NOT NULL DEFAULT 'processed',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE tags (
            id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE,
            normalized_name TEXT NOT NULL
        );
        CREATE TABLE message_tags (
            message_id INTEGER NOT NULL, tag_id INTEGER NOT NULL, type TEXT NOT NULL,
            PRIMARY KEY (message_id, tag_id)
        );
        """
    )
    raw.commit()
    raw.close()
    return str(db)


def _patch_client(tmp_path):
    """构造注入 client/conn/indexer 的受测模型：PATCH 走共享 service。"""
    import sqlite3

    from app.web.app import create_app as _create

    db_path = _make_schema_db(tmp_path)
    raw = sqlite3.connect(db_path)
    raw.execute(
        "INSERT INTO messages (id, source_chat_id, source_message_id, media_type, "
        "original_text, rating, status, target_chat_id, target_message_id, rendered_text) "
        "VALUES (1, -1001, 1, 'photo', '正文一', 4, 'archived', -1005, 99, '正文一')"
    )
    raw.commit()
    raw.close()

    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row

    class Client:
        async def edit_message(self, chat_id, message_id, text):
            pass

    class Indexer:
        def schedule(self):
            pass

    cfg = _config(database_path=db_path, web_token="secret-token")
    app = _create(cfg, client=Client(), conn=conn, indexer=Indexer())
    tc = TestClient(app)
    tc.post("/api/v1/auth/login", json={"token": "secret-token"})
    yield tc
    conn.close()


@pytest.fixture
def patch_client(tmp_path):
    yield from _patch_client(tmp_path)


def test_messages_list_and_detail(tmp_path):
    db = _make_schema_db(tmp_path)
    with _logged_client(db) as client:
        resp = client.get("/api/v1/messages")
        assert resp.status_code == 200
        assert resp.json() == {"items": [], "total": 0, "limit": 30, "offset": 0}


def test_messages_patch_updates_via_shared_service(patch_client):
    resp = patch_client.patch("/api/v1/messages/1", json={"add_tags": ["游戏"]})
    assert resp.status_code == 200
    body = resp.json()
    assert body["tags"] == [{"name": "游戏", "type": "manual"}]


def test_messages_patch_requires_action(patch_client):
    resp = patch_client.patch("/api/v1/messages/1", json={})
    assert resp.status_code == 422


def test_messages_patch_not_found(patch_client):
    resp = patch_client.patch("/api/v1/messages/999", json={"rating": 3})
    assert resp.status_code == 404


def _seeded_messages_db(tmp_path):
    """建一张带 2 条消息(含 tag/target)的真实 schema 库。"""
    import sqlite3

    db = _make_schema_db(tmp_path, name="seeded.sqlite")
    conn = sqlite3.connect(db)
    conn.execute(
        "INSERT INTO tags (name, normalized_name) VALUES ('游戏', '游戏'), ('MOD', 'mod')"
    )
    conn.execute(
        "INSERT INTO messages (id, source_chat_id, source_message_id, media_type, "
        "original_text, rating, status, target_chat_id, target_message_id) "
        "VALUES (1, -1001, 1, 'photo', '截图', 4, 'archived', -1005, 11),"
        "      (2, -1002, 2, 'text', 'MOD 说明', 0, 'archived', -1005, 12)"
    )
    conn.execute("INSERT INTO message_tags (message_id, tag_id, type) VALUES (1, 1, 'source')")
    conn.commit()
    conn.close()
    return db


def test_tags_endpoint(tmp_path):
    db = _seeded_messages_db(tmp_path)
    with _logged_client(db) as client:
        resp = client.get("/api/v1/tags")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 2
        assert {"游戏", "MOD"} == {t["name"] for t in body["items"]}
        games = next(t for t in body["items"] if t["name"] == "游戏")
        assert games["count"] == 1


def test_messages_list_filter_and_tags(tmp_path):
    db = _seeded_messages_db(tmp_path)
    with _logged_client(db) as client:
        resp = client.get("/api/v1/messages?tag=游戏")
        body = resp.json()
        assert body["total"] == 1
        assert body["items"][0]["id"] == 1
        assert body["items"][0]["tags"] == [{"name": "游戏", "type": "source"}]
        assert body["items"][0]["thumb"]["available"] is False




def test_reset_database_uses_request_owned_connection(tmp_path):
    db = _seeded_messages_db(tmp_path)
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE schema_version (version TEXT PRIMARY KEY)")
    conn.execute("INSERT INTO schema_version VALUES ('0005_target_fields')")
    conn.commit()
    conn.close()

    cfg = _config(database_path=db, config_path=str(tmp_path / "config.yaml"))
    (tmp_path / "config.yaml").write_text("telegram: {}\n", encoding="utf-8")
    with TestClient(create_app(cfg, conn=sqlite3.connect(db))) as client:
        client.post("/api/v1/auth/login", json={"token": "secret-token"})
        response = client.post(
            "/api/v1/ops/reset-database", json={"confirm": "RESET DATABASE"}
        )
    assert response.status_code == 200
    assert response.json()["restart_required"] is True
    check = sqlite3.connect(db)
    assert check.execute("SELECT COUNT(*) FROM messages").fetchone()[0] == 0
    assert check.execute("SELECT version FROM schema_version").fetchone()[0] == "0005_target_fields"
    check.close()
    db = _make_schema_db(tmp_path, name="targets.sqlite")
    conn = sqlite3.connect(db)
    conn.executescript(
        """
        CREATE TABLE message_targets (
            id INTEGER PRIMARY KEY,
            message_id INTEGER NOT NULL,
            target_chat_id INTEGER NOT NULL,
            target_message_id INTEGER,
            target_url TEXT,
            status TEXT NOT NULL,
            original_text TEXT NOT NULL DEFAULT '',
            original_html TEXT NOT NULL DEFAULT '',
            rendered_text TEXT NOT NULL DEFAULT '',
            rating INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE target_tags (
            target_id INTEGER NOT NULL, tag_id INTEGER NOT NULL, type TEXT NOT NULL
        );
        INSERT INTO messages (id, source_chat_id, source_message_id, media_type, status)
        VALUES (72, -1001, 72, 'text', 'processed');
        INSERT INTO message_targets (
            id, message_id, target_chat_id, target_message_id, status, original_text
        )
        VALUES (101, 72, -1005, 201, 'archived', 'A copy'),
               (102, 72, -1006, 202, 'deleted', 'B copy');
        """
    )
    conn.commit()
    conn.close()
    with _logged_client(db) as client:
        active = client.get("/api/v1/messages?status=active").json()
        assert active["total"] == 1
        assert active["items"][0]["id"] == 72
        assert active["items"][0]["material_id"] == "target:101"
        assert active["items"][0]["target_chat_id"] == -1005

        deleted = client.get("/api/v1/messages?status=deleted").json()
        assert deleted["total"] == 1
        assert deleted["items"][0]["material_id"] == "target:102"

        filtered = client.get("/api/v1/messages?status=all&target_chat_id=-1006").json()
        assert filtered["total"] == 1
        assert filtered["items"][0]["material_id"] == "target:102"
def test_reset_clears_thumbnail_cache(tmp_path):
    db = _seeded_messages_db(tmp_path)
    thumbs = tmp_path / "thumbs"
    thumbs.mkdir()
    (thumbs / "-1005_1.jpg").write_bytes(b"old")
    from app.web.backup import reset_database

    reset_database(Path(db))
    assert not (thumbs / "-1005_1.jpg").exists()


def test_messages_thumb_without_client_404(tmp_path):
    db = _seeded_messages_db(tmp_path)
    cfg = _config(database_path=db, web_token="secret-token")
    from app.web.app import create_app as _create

    with TestClient(_create(cfg, client=None, conn=None)) as client:
        client.post("/api/v1/auth/login", json={"token": "secret-token"})
        assert client.get("/api/v1/messages/1/thumb").status_code == 404


def test_restore_rejects_invalid_database_backup(tmp_path):
    """恢复前校验备份文件：坏备份必须 400 且不碰当前库。"""
    db = _seeded_messages_db(tmp_path)
    before = sqlite3.connect(db).execute("SELECT COUNT(*) FROM messages").fetchone()[0]
    bad = Path(db).parent / f"{Path(db).name}.20260101T000000Z.bak"
    bad.write_text("not a sqlite database", encoding="utf-8")
    cfg = _config(database_path=db, config_path=str(tmp_path / "config.yaml"))
    (tmp_path / "config.yaml").write_text("telegram: {}\n", encoding="utf-8")

    with TestClient(create_app(cfg)) as client:
        client.post("/api/v1/auth/login", json={"token": "secret-token"})
        resp = client.post("/api/v1/ops/restore", json={"name": bad.name})

    assert resp.status_code == 400
    after = sqlite3.connect(db).execute("SELECT COUNT(*) FROM messages").fetchone()[0]
    assert after == before


def test_restore_valid_backup_pauses_queue(tmp_path):
    """合法恢复照常进行，但队列要被暂停以等待重启。"""
    from app.web.backup import backup_database

    db = _seeded_messages_db(tmp_path)
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE schema_version (version TEXT PRIMARY KEY)")
    conn.execute("INSERT INTO schema_version VALUES ('0006_message_template')")
    conn.commit()
    conn.close()
    backup_path = backup_database(Path(db))
    cfg = _config(database_path=db, config_path=str(tmp_path / "config.yaml"))
    (tmp_path / "config.yaml").write_text("telegram: {}\n", encoding="utf-8")

    class FakeQueue:
        def __init__(self):
            self.paused = False

        def pause(self):
            self.paused = True

        def is_paused(self):
            return self.paused

    queue = FakeQueue()
    with TestClient(create_app(cfg, queue=queue)) as client:
        client.post("/api/v1/auth/login", json={"token": "secret-token"})
        resp = client.post("/api/v1/ops/restore", json={"name": backup_path.name})

    assert resp.status_code == 200
    assert resp.json()["restart_required"] is True
    assert queue.paused is True


def test_delete_backup_removes_file(tmp_path):
    """备份可单个删除：文件消失、列表同步减少。"""
    from app.web.backup import backup_database

    db = _seeded_messages_db(tmp_path)
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE schema_version (version TEXT PRIMARY KEY)")
    conn.commit()
    conn.close()
    backup_path = backup_database(Path(db))
    cfg = _config(database_path=db, config_path=str(tmp_path / "config.yaml"))
    (tmp_path / "config.yaml").write_text("telegram: {}\n", encoding="utf-8")

    with TestClient(create_app(cfg)) as client:
        client.post("/api/v1/auth/login", json={"token": "secret-token"})
        listed = client.get("/api/v1/ops/backups").json()["items"]
        assert [item["name"] for item in listed] == [backup_path.name]

        resp = client.delete(f"/api/v1/ops/backups/{backup_path.name}")
        assert resp.status_code == 200
        assert resp.json()["ok"] is True

        remaining = client.get("/api/v1/ops/backups").json()["items"]
        assert remaining == []

    assert not backup_path.exists()


def test_delete_backup_rejects_bad_name(tmp_path):
    """非法名与不存在的备份分别 400 / 404，不动其他文件。"""
    db = _seeded_messages_db(tmp_path)
    from app.web.backup import backup_database

    backup_path = backup_database(Path(db))
    cfg = _config(database_path=db, config_path=str(tmp_path / "config.yaml"))
    (tmp_path / "config.yaml").write_text("telegram: {}\n", encoding="utf-8")

    with TestClient(create_app(cfg)) as client:
        client.post("/api/v1/auth/login", json={"token": "secret-token"})
        assert client.delete("/api/v1/ops/backups/not-a-bak").status_code == 400
        assert client.delete("/api/v1/ops/backups/missing.bak").status_code == 404

    assert backup_path.exists()
