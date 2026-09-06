"""Web API：鉴权 + stats 读取端点。"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta
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
        assert body["targets"] == [
            {"chat_id": -1005, "count": 2, "name": ""},
            {"chat_id": -1006, "count": 1, "name": ""},
        ]


def test_stats_targets_carry_config_names(tmp_path, seeded_db):
    """目录筛选要显示人读名称：stats 把配置里的目标名一并返回，缺失为空串。"""
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        "telegram:\n"
        "  target_channels:\n"
        "    - chat_id: -1005\n"
        "      name: 日常归档\n",
        encoding="utf-8",
    )
    cfg = _config(database_path=seeded_db, config_path=str(config_file), web_token="secret-token")
    with TestClient(create_app(cfg)) as client:
        client.post("/api/v1/auth/login", json={"token": "secret-token"})
        body = client.get("/api/v1/stats").json()

    names = {t["chat_id"]: t["name"] for t in body["targets"]}
    assert names[-1005] == "日常归档"
    assert names[-1006] == ""


def test_logout_invalidates_session(tmp_path):
    with _client(tmp_path) as client:
        client.post("/api/v1/auth/login", json={"token": "secret-token"})
        assert client.post("/api/v1/auth/logout").status_code == 200
        assert client.get("/api/v1/stats").status_code == 401


def test_health_requires_login(tmp_path):
    with _client(tmp_path) as client:
        assert client.get("/api/v1/health").status_code == 401


def _utc_text(local_dt: datetime) -> str:
    """本地墙钟时间 → SQLite CURRENT_TIMESTAMP 的 UTC 文本（YYYY-MM-DD HH:MM:SS）。"""
    return local_dt.astimezone(UTC).strftime("%Y-%m-%d %H:%M:%S")


def _seeded_trend_db(tmp_path) -> str:
    """归档时间按本地日散布的库：今天 2 条、昨天 1 条、40 天前 1 条，
    另有今天 1 条 processed（不计入趋势）。"""
    db = _make_schema_db(tmp_path, name="trend.sqlite")
    noon = datetime.now().astimezone().replace(hour=12, minute=0, second=0, microsecond=0)
    rows = [
        (1, noon, "archived"),
        (2, noon, "archived"),
        (3, noon - timedelta(days=1), "archived"),
        (4, noon - timedelta(days=40), "archived"),
        (5, noon, "processed"),
    ]
    raw = sqlite3.connect(db)
    for mid, at, status in rows:
        raw.execute(
            "INSERT INTO messages (id, source_chat_id, source_message_id, media_type, "
            "status, created_at) VALUES (?, ?, ?, 'text', ?, ?)",
            (mid, -1001, mid, status, _utc_text(at)),
        )
    raw.commit()
    raw.close()
    return db


def test_stats_trend_counts_by_local_day(tmp_path):
    """每日归档量按本地日分组：只计 archived、缺数日补 0、窗口外不出现。"""
    db = _seeded_trend_db(tmp_path)
    with _logged_client(db) as client:
        body = client.get("/api/v1/stats/trend?days=5").json()
    today = datetime.now().astimezone().date()
    assert [i["date"] for i in body["items"]] == [
        (today - timedelta(days=n)).isoformat() for n in (4, 3, 2, 1, 0)
    ]
    assert [i["count"] for i in body["items"]] == [0, 0, 0, 1, 2]


def test_stats_trend_default_and_clamp(tmp_path):
    """?days 缺省 30，越界收敛到 1..90。"""
    db = _seeded_trend_db(tmp_path)
    with _logged_client(db) as client:
        assert len(client.get("/api/v1/stats/trend").json()["items"]) == 30
        assert len(client.get("/api/v1/stats/trend?days=0").json()["items"]) == 1
        assert len(client.get("/api/v1/stats/trend?days=999").json()["items"]) == 90


def test_stats_activity_endpoint(tmp_path):
    """近期活动：归档事件 + 任务失败按时间倒序混排；limit 收敛、queue 同 /stats 口径。"""
    db = _seeded_messages_db(tmp_path)
    import sqlite3

    conn = sqlite3.connect(db)
    # _make_schema_db 不跑迁移，这里手动建 task_failures（与迁移 0008 同构）
    conn.execute(
        "CREATE TABLE IF NOT EXISTS task_failures ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, task TEXT NOT NULL, "
        "error TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)"
    )
    conn.execute(
        "INSERT INTO task_failures (task, error, created_at) "
        "VALUES ('auto_backup', 'boom', '2020-01-01 00:00:00')"
    )
    conn.commit()
    conn.close()
    with _logged_client(db) as client:
        body = client.get("/api/v1/stats/activity").json()
        items = body["items"]
        # 消息 created_at 为当前时间，晚于 2020 年的失败记录 → 归档在前、失败殿后
        assert items[0]["kind"] == "archived"
        assert items[0]["title"] and items[0]["source"] == ""
        assert items[-1]["kind"] == "failure"
        assert items[-1]["task"] == "auto_backup"
        assert items[-1]["error"] == "boom"
        assert body["queue"] == {"pending": 0, "processing": 0, "success": 0, "failed": 0}

        clamped = client.get("/api/v1/stats/activity?limit=1").json()
        assert len(clamped["items"]) == 1
        assert len(client.get("/api/v1/stats/activity?limit=999").json()["items"]) == 3


def test_stats_trend_requires_login(tmp_path):
    db = _seeded_trend_db(tmp_path)
    cfg = _config(database_path=db, web_token="secret-token")
    with TestClient(create_app(cfg)) as client:
        assert client.get("/api/v1/stats/trend").status_code == 401


def test_stats_trend_empty_database(tmp_path):
    """空库：全 0 的连续日期序列，不抛错。"""
    db = _make_schema_db(tmp_path, name="empty.sqlite")
    with _logged_client(db) as client:
        body = client.get("/api/v1/stats/trend").json()
    assert len(body["items"]) == 30
    assert all(i["count"] == 0 for i in body["items"])
    assert len({i["date"] for i in body["items"]}) == 30


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
        assert resp.json() == {
            "items": [],
            "total": 0,
            "limit": 30,
            "offset": 0,
            "facets": {"media_type": {}, "targets": [], "tags": []},
        }


def test_messages_facets_reflect_filters(tmp_path):
    """分面计数：体例/来源剔除本维度约束，标签为共现口径（已选标签作 AND 约束）。"""
    db = _seeded_messages_db(tmp_path)
    # 追加共现场景：消息 2 同时挂「旅行」，与消息 1 的「游戏」不共现
    import sqlite3

    conn = sqlite3.connect(db)
    conn.execute("INSERT INTO tags (name, normalized_name) VALUES ('旅行', '旅行')")
    conn.execute(
        "INSERT INTO message_tags (message_id, tag_id, type) "
        "SELECT 2, id, 'source' FROM tags WHERE name = '旅行'"
    )
    conn.commit()
    conn.close()
    with _logged_client(db) as client:
        body = client.get("/api/v1/messages").json()
        facets = body["facets"]
        assert facets["media_type"] == {"photo": 1, "text": 1}
        assert {t["chat_id"] for t in facets["targets"]} == {-1005}
        assert {t["name"]: t["count"] for t in facets["tags"]} == {"游戏": 1, "旅行": 1}

        # 带 q=MOD：media 分面里 q 仍生效，只剩 text；只剩与 MOD 消息共现的「旅行」
        facets = client.get("/api/v1/messages?q=MOD").json()["facets"]
        assert facets["media_type"] == {"text": 1}
        assert facets["tags"] == [{"name": "旅行", "count": 1}]

        # 带 tag=游戏：target 分面应忽略标签约束仍报 -1005；media 分面只有 photo
        facets = client.get("/api/v1/messages?tag=游戏").json()["facets"]
        assert facets["media_type"] == {"photo": 1}
        assert facets["targets"] == [{"chat_id": -1005, "count": 1}]
        # 标签共现口径：「游戏」自身保持命中数，不与它共现的「旅行」不出现（前端计 0）
        assert facets["tags"] == [{"name": "游戏", "count": 1}]

        # 带 media_type=text：标签与 target 分面按 text 生效，
        # media 分面自身剔除后仍给出全量分布
        facets = client.get("/api/v1/messages?media_type=text").json()["facets"]
        assert facets["media_type"] == {"photo": 1, "text": 1}
        assert facets["tags"] == [{"name": "旅行", "count": 1}]
        assert facets["targets"] == [{"chat_id": -1005, "count": 1}]

        # 多标签 AND 交集：游戏∧旅行无共现消息，分面为空
        facets = client.get("/api/v1/messages?tag=游戏&tag=旅行").json()["facets"]
        assert facets["tags"] == []


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


def test_messages_list_multi_tag_is_intersection(tmp_path):
    """?tag 可重复多值：同时带全部指定标签才命中（AND 语义）。"""
    db = _make_schema_db(tmp_path, name="multitag.sqlite")
    conn = sqlite3.connect(db)
    conn.execute(
        "INSERT INTO tags (name, normalized_name) VALUES ('游戏', '游戏'), ('MOD', 'mod')"
    )
    conn.execute(
        "INSERT INTO messages (id, source_chat_id, source_message_id, media_type, "
        "original_text, status) "
        "VALUES (1, -1001, 1, 'photo', '双标签', 'archived'),"
        "      (2, -1002, 2, 'text', '仅游戏', 'archived'),"
        "      (3, -1003, 3, 'text', '仅MOD', 'archived')"
    )
    # 消息 1：游戏+MOD；消息 2：游戏；消息 3：MOD
    conn.executescript(
        """
        INSERT INTO message_tags (message_id, tag_id, type) VALUES
            (1, 1, 'source'), (1, 2, 'source'),
            (2, 1, 'source'),
            (3, 2, 'source');
        """
    )
    conn.commit()
    conn.close()
    with _logged_client(db) as client:
        both = client.get("/api/v1/messages?tag=游戏&tag=MOD").json()
        assert both["total"] == 1
        assert both["items"][0]["id"] == 1

        single = client.get("/api/v1/messages?tag=游戏").json()
        assert single["total"] == 2

        missing = client.get("/api/v1/messages?tag=游戏&tag=不存在").json()
        assert missing["total"] == 0




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
def test_reset_rebuilds_fts_index(tmp_path):
    """重置后 FTS 索引必须可用：清空会破坏 FTS 内部结构，需 rebuild 兜底。"""
    from app.web.backup import reset_database

    db = _migrated_db(tmp_path)
    conn = sqlite3.connect(db)
    _insert_message(conn, 1, "重置前的旧消息")
    conn.commit()
    reset_database(Path(db))
    # 重置后新消息经触发器写 FTS 不应报 invalid fts5 file format
    conn.execute(
        "INSERT INTO messages (id, source_chat_id, source_message_id, "
        "original_text, rendered_text, status) VALUES (2, -1001, 2, "
        "'重置后的新消息', '重置后的新消息', 'archived')"
    )
    hits = conn.execute(
        "SELECT rowid FROM messages_fts WHERE messages_fts MATCH '\"重置后的\"'"
    ).fetchall()
    assert hits == [(2,)]
    conn.close()


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


def test_run_backup_now(tmp_path):
    """POST /ops/backups/run 立即落盘一份库备份；无调度器时走本地回退。"""
    db = _seeded_messages_db(tmp_path)
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE schema_version (version TEXT PRIMARY KEY)")
    conn.commit()
    conn.close()
    cfg = _config(database_path=db, config_path=str(tmp_path / "config.yaml"))
    (tmp_path / "config.yaml").write_text("telegram: {}\n", encoding="utf-8")

    with TestClient(create_app(cfg)) as client:
        client.post("/api/v1/auth/login", json={"token": "secret-token"})
        resp = client.post("/api/v1/ops/backups/run")
        assert resp.status_code == 200
        name = resp.json()["name"]
        assert name.endswith(".bak")

        listed = client.get("/api/v1/ops/backups").json()["items"]
        assert name in [item["name"] for item in listed]
        assert (Path(db).parent / name).exists()


def test_run_backup_now_uses_scheduler(tmp_path):
    """app.state.auto_backup 存在时走调度器（run_once 被调用）。"""
    from types import SimpleNamespace

    db = _seeded_messages_db(tmp_path)
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE schema_version (version TEXT PRIMARY KEY)")
    conn.commit()
    conn.close()
    cfg = _config(database_path=db, config_path=str(tmp_path / "config.yaml"))
    (tmp_path / "config.yaml").write_text("telegram: {}\n", encoding="utf-8")

    calls = []

    async def fake_run_once():
        calls.append(1)
        return Path(db).with_name(f"{Path(db).name}.manual.bak")

    scheduler = SimpleNamespace(run_once=fake_run_once)
    app = create_app(cfg, auto_backup=scheduler)

    with TestClient(app) as client:
        client.post("/api/v1/auth/login", json={"token": "secret-token"})
        resp = client.post("/api/v1/ops/backups/run")
        assert resp.status_code == 200
        assert resp.json()["name"].endswith(".manual.bak")
    assert calls == [1]


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


# ---- FTS5 全文搜索（0009 迁移 + LIKE 回退） ----


def _migrated_db(tmp_path, name="fts.sqlite") -> str:
    """跑完整迁移的真实 schema 库：messages_fts 与同步触发器都已就位。"""
    from app.database.migrate import apply_migrations, open_db

    db = tmp_path / name
    conn = open_db(str(db))
    apply_migrations(conn)
    conn.close()
    return str(db)


def _insert_message(conn, id_, text, file_name=""):
    conn.execute(
        "INSERT INTO messages (id, source_chat_id, source_message_id, media_type, "
        "original_text, rendered_text, file_name, status) "
        "VALUES (?, -1001, ?, 'text', ?, ?, ?, 'archived')",
        (id_, id_, text, text, file_name),
    )


def test_fts_search_matches_cjk_and_latin(tmp_path):
    db = _migrated_db(tmp_path)
    conn = sqlite3.connect(db)
    _insert_message(conn, 1, "游戏攻略分享")
    _insert_message(conn, 2, "Game Guide Tonight")
    conn.commit()
    conn.close()
    with _logged_client(db) as client:
        body = client.get("/api/v1/messages?q=游戏").json()
        assert body["total"] == 1
        assert body["items"][0]["id"] == 1
        latin = client.get("/api/v1/messages?q=game").json()
        assert [i["id"] for i in latin["items"]] == [2]


def test_fts_search_prefix_match(tmp_path):
    """「游戏」前缀命中「游戏机」；FTS 不需要写出完整词。"""
    db = _migrated_db(tmp_path)
    conn = sqlite3.connect(db)
    _insert_message(conn, 1, "新游戏机开箱")
    _insert_message(conn, 2, "今天天气不错")
    conn.commit()
    conn.close()
    with _logged_client(db) as client:
        body = client.get("/api/v1/messages?q=游戏").json()
        assert [i["id"] for i in body["items"]] == [1]
        assert client.get("/api/v1/messages?q=天气").json()["total"] == 1


def test_fts_search_multi_term_is_and(tmp_path):
    """多词 AND：两词都在才命中。"""
    db = _migrated_db(tmp_path)
    conn = sqlite3.connect(db)
    _insert_message(conn, 1, "游戏攻略 include 地图")
    _insert_message(conn, 2, "游戏攻略 但没有另一个词")
    _insert_message(conn, 3, "只有地图")
    conn.commit()
    conn.close()
    with _logged_client(db) as client:
        body = client.get("/api/v1/messages?q=游戏+地图").json()
        assert [i["id"] for i in body["items"]] == [1]


def test_fts_search_special_chars_do_not_500(tmp_path):
    """引号/括号/通配符/百分号等不破坏 MATCH 语法，也不触发 500。"""
    db = _migrated_db(tmp_path)
    conn = sqlite3.connect(db)
    _insert_message(conn, 1, "100% 正品 (未拆封)")
    conn.commit()
    conn.close()
    with _logged_client(db) as client:
        for q in ['"', "(", "NEAR(", "%", "*", '"未拆封"', "游戏 AND ("]:
            resp = client.get(f"/api/v1/messages?q={q}")
            assert resp.status_code == 200, q
        # 100% 是一个 token，前缀查询 "100%*" 命中它
        assert client.get("/api/v1/messages?q=100%25").json()["total"] == 1


def test_fts_search_falls_back_to_like_without_fts_table(tmp_path):
    """FTS 表缺失（模拟无 FTS5 / 未跑 0009）时回退 LIKE，搜索不 500。"""
    db = _make_schema_db(tmp_path, name="nofsts.sqlite")
    conn = sqlite3.connect(db)
    _insert_message(conn, 1, "游戏攻略分享")
    conn.commit()
    conn.close()
    with _logged_client(db) as client:
        body = client.get("/api/v1/messages?q=攻略").json()
        assert body["total"] == 1
        assert body["items"][0]["id"] == 1


def test_fts_search_falls_back_after_table_dropped(tmp_path):
    """迁移过的库把 messages_fts 手动删掉后仍可搜索（运行期回退）。"""
    db = _migrated_db(tmp_path, name="dropped.sqlite")
    conn = sqlite3.connect(db)
    _insert_message(conn, 1, "游戏攻略分享")
    conn.commit()
    conn.execute("DROP TABLE messages_fts")
    conn.commit()
    conn.close()
    with _logged_client(db) as client:
        body = client.get("/api/v1/messages?q=攻略").json()
        assert body["total"] == 1
        assert body["items"][0]["id"] == 1


def test_fts_facets_follow_search(tmp_path):
    """分面计数与 q= 同口径（FTS 路径下同样生效）。"""
    db = _migrated_db(tmp_path)
    conn = sqlite3.connect(db)
    _insert_message(conn, 1, "游戏攻略")
    _insert_message(conn, 2, "旅行日记")
    conn.execute("INSERT INTO tags (name, normalized_name) VALUES ('游戏', '游戏')")
    conn.execute("INSERT INTO message_tags (message_id, tag_id, type) VALUES (1, 1, 'source')")
    conn.commit()
    conn.close()
    with _logged_client(db) as client:
        facets = client.get("/api/v1/messages?q=游戏").json()["facets"]
        assert facets["tags"] == [{"name": "游戏", "count": 1}]


def test_fts_search_matches_copy_text(tmp_path):
    """joined 主路径搜副本文本：只有副本 original_text 里出现的词也能命中。"""
    db = _migrated_db(tmp_path)
    conn = sqlite3.connect(db)
    _insert_message(conn, 1, "父表正文里没有目标词汇")
    conn.execute(
        "INSERT INTO message_targets (message_id, target_chat_id, status, "
        "original_text, rendered_text) VALUES (1, -1005, 'archived', "
        "'副本独有词组内容', '副本独有词组内容')"
    )
    conn.commit()
    conn.close()
    with _logged_client(db) as client:
        body = client.get("/api/v1/messages?q=独有词组").json()
        assert body["total"] == 1
        assert body["items"][0]["id"] == 1


def test_ops_failures_endpoint(tmp_path):
    """/ops/failures：最近失败记录倒序 + limit 收敛 + 需要登录。"""
    db = _seeded_messages_db(tmp_path)
    import sqlite3

    conn = sqlite3.connect(db)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS task_failures ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, task TEXT NOT NULL, "
        "error TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)"
    )
    conn.executemany(
        "INSERT INTO task_failures (task, error, created_at) VALUES (?, ?, ?)",
        [
            ("auto_backup", "first", "2020-01-01 00:00:00"),
            ("backup_upload", "second", "2021-06-01 12:30:00"),
        ],
    )
    conn.commit()
    conn.close()
    # ops 路由仅在 config_path 存在时挂载（与其他 /ops 端点一致）
    cfg = _config(database_path=db, config_path=str(tmp_path / "config.yaml"))
    (tmp_path / "config.yaml").write_text("telegram: {}\n", encoding="utf-8")
    with TestClient(create_app(cfg)) as client:
        client.post("/api/v1/auth/login", json={"token": "secret-token"})
        body = client.get("/api/v1/ops/failures").json()
        assert [i["task"] for i in body["items"]] == ["backup_upload", "auto_backup"]
        assert body["items"][0]["error"] == "second"

        assert len(client.get("/api/v1/ops/failures?limit=1").json()["items"]) == 1
        assert len(client.get("/api/v1/ops/failures?limit=999").json()["items"]) == 2
        assert client.get("/api/v1/ops/failures?limit=0").json()["items"]

    # 未登录需要 401
    with TestClient(create_app(cfg)) as client:
        assert client.get("/api/v1/ops/failures").status_code == 401

def _ops_client(tmp_path, db):
    """ops 路由需要 config_path 才挂载（与备份测试同一套件约定）。"""
    cfg = _config(database_path=db, config_path=str(tmp_path / "config.yaml"))
    (tmp_path / "config.yaml").write_text("telegram: {}\n", encoding="utf-8")
    client = TestClient(create_app(cfg))
    client.post("/api/v1/auth/login", json={"token": "secret-token"})
    return client


def test_ops_export_csv(tmp_path):
    """/ops/export?format=csv：中文表头 + BOM，字段完整，下载头正确。"""
    db = _seeded_messages_db(tmp_path)
    with _ops_client(tmp_path, db) as client:
        resp = client.get("/api/v1/ops/export?format=csv")
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/csv")
        assert "attachment" in resp.headers["content-disposition"]
        body = resp.content
        assert body.startswith(b"\xef\xbb\xbf")  # UTF-8 BOM
        import csv as csv_mod
        import io as io_mod

        text = body.decode("utf-8-sig")
        rows = list(csv_mod.reader(io_mod.StringIO(text)))
        assert rows[0][0] == "编号"
        assert len(rows) == 3  # 表头 + 2 条归档
        data = dict(zip(rows[0], rows[1], strict=True))
        assert data["编号"] == "1"
        assert data["类型"] == "photo"
        assert data["标签"] == "#游戏"


def test_ops_export_json_shape(tmp_path):
    """/ops/export?format=json：exported_at + items 数组，字段含 targets/tags。"""
    db = _seeded_messages_db(tmp_path)
    with _ops_client(tmp_path, db) as client:
        resp = client.get("/api/v1/ops/export?format=json")
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("application/json")
        body = resp.json()
        assert body["items"][0]["id"] == 1
        assert body["items"][0]["tags"][0]["name"] == "游戏"
        assert "exported_at" in body


def test_ops_export_respects_filters(tmp_path):
    """导出支持 /messages 同款过滤：q= 只导命中条目。"""
    db = _seeded_messages_db(tmp_path)
    with _ops_client(tmp_path, db) as client:
        body = client.get("/api/v1/ops/export?format=json&q=MOD").json()
        assert [i["id"] for i in body["items"]] == [2]


def test_ops_export_rejects_bad_format_and_requires_auth(tmp_path):
    db = _seeded_messages_db(tmp_path)
    with _ops_client(tmp_path, db) as client:
        assert client.get("/api/v1/ops/export?format=xlsx").status_code == 400
        assert client.get("/api/v1/ops/export?format=csv&status=bogus").status_code == 400
    cfg = _config(database_path=db, config_path=str(tmp_path / "config.yaml"))
    with TestClient(create_app(cfg)) as plain:
        assert plain.get("/api/v1/ops/export?format=csv").status_code == 401
