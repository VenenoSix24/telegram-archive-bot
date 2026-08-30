"""Web API：鉴权 + stats 读取端点。"""

from __future__ import annotations

import sqlite3

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
            status TEXT NOT NULL DEFAULT 'processed'
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
        INSERT INTO messages (id, source_chat_id, source_message_id, media_type, status)
        VALUES (1, -1001, 1, 'photo', 'archived'),
               (2, -1001, 2, 'video', 'archived'),
               (3, -1002, 1, 'text', 'archived'),
               (4, -1002, 2, 'text', 'processed');
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


def test_logout_invalidates_session(tmp_path):
    with _client(tmp_path) as client:
        client.post("/api/v1/auth/login", json={"token": "secret-token"})
        assert client.post("/api/v1/auth/logout").status_code == 200
        assert client.get("/api/v1/stats").status_code == 401


def test_health_requires_login(tmp_path):
    with _client(tmp_path) as client:
        assert client.get("/api/v1/health").status_code == 401
