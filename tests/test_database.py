"""数据库 schema、迁移幂等与唯一约束。"""

from __future__ import annotations

import sqlite3

import pytest

from app.database.migrate import MIGRATIONS_DIR, _version_num, apply_migrations, open_db


@pytest.fixture
def conn(tmp_path) -> sqlite3.Connection:
    db = open_db(tmp_path / "test.sqlite")
    apply_migrations(db)
    return db


def _tables(conn) -> set[str]:
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()
    return {row[0] for row in rows}


def test_initial_schema_tables(conn):
    tables = _tables(conn)
    assert {
        "channels",
        "messages",
        "tags",
        "message_tags",
        "queue",
        "settings",
        "schema_version",
    } <= tables


def test_migrations_idempotent(conn):
    assert apply_migrations(conn) == []
    assert apply_migrations(conn) == []


def test_source_unique_constraint(conn):
    conn.execute(
        "INSERT INTO messages (source_chat_id, source_message_id) VALUES (-1001, 5)"
    )
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO messages (source_chat_id, source_message_id) VALUES (-1001, 5)"
        )


# ---- PRAGMA user_version 迁移 ----


def _user_version(conn) -> int:
    return conn.execute("PRAGMA user_version").fetchone()[0]


def test_latest_user_version(conn):
    assert _user_version(conn) > 0
    assert _user_version(conn) == _version_num(sorted(MIGRATIONS_DIR.glob("*.sql"))[-1].stem)


def test_fresh_db_reaches_latest_version(tmp_path):
    db = open_db(tmp_path / "fresh.sqlite")
    newly = apply_migrations(db)
    assert len(newly) > 0
    assert apply_migrations(db) == []  # 重开不重跑
    assert _user_version(db) == _version_num(sorted(MIGRATIONS_DIR.glob("*.sql"))[-1].stem)


def _latest_version_num() -> int:
    return _version_num(sorted(MIGRATIONS_DIR.glob("*.sql"))[-1].stem)


def test_legacy_db_without_user_version_migrates_without_data_loss(tmp_path):
    """旧库：schema_version 有记录、user_version=0、数据在库——升级不改数据。"""
    path = tmp_path / "legacy.sqlite"
    db = open_db(path)
    db.executescript(
        """
        CREATE TABLE schema_version (
            version TEXT PRIMARY KEY, applied_at TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE channels (id INTEGER PRIMARY KEY, title TEXT);
        CREATE TABLE messages (
            id INTEGER PRIMARY KEY,
            source_chat_id INTEGER NOT NULL,
            source_message_id INTEGER NOT NULL,
            media_type TEXT NOT NULL DEFAULT 'text',
            original_text TEXT NOT NULL DEFAULT '',
            rendered_text TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'processed',
            target_chat_id INTEGER);
        INSERT INTO schema_version (version) VALUES ('0001_initial');
        INSERT INTO channels (id, title) VALUES (1, 'demo');
        INSERT INTO messages (source_chat_id, source_message_id) VALUES (-1001, 5);
        """
    )
    db.commit()

    newly = apply_migrations(db)
    # 旧库已记录 0001：基线对齐不重放它，只补齐之后的迁移
    assert "0001_initial" not in newly
    assert _user_version(db) == _latest_version_num()
    assert db.execute("SELECT title FROM channels WHERE id=1").fetchone()[0] == "demo"
    assert db.execute("SELECT COUNT(*) FROM messages").fetchone()[0] == 1
    # 新增迁移的表可用（task_failures）
    db.execute("INSERT INTO task_failures (task, error) VALUES ('t', 'e')")
    db.commit()
    db.close()


def test_legacy_db_baseline_no_rerun_of_old_ddl(tmp_path):
    """schema_version 记录齐全的旧库升级时，DDL 不重放（幂等即可，但版本列表为空）。"""
    path = tmp_path / "legacy2.sqlite"
    db = open_db(path)
    versions = [f.stem for f in sorted(MIGRATIONS_DIR.glob("*.sql"))]
    db.execute(
        "CREATE TABLE schema_version ("
        "version TEXT PRIMARY KEY, applied_at TEXT DEFAULT CURRENT_TIMESTAMP)"
    )
    db.executemany(
        "INSERT INTO schema_version (version) VALUES (?)", [(v,) for v in versions]
    )
    # 故意不放任何业务表，若 DDL 被重放就会建出表——用它断言没重放
    db.commit()
    apply_migrations(db)
    assert _user_version(db) == _latest_version_num()
    assert db.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='channels'"
    ).fetchone()[0] == 0
    db.close()


# ---- 0009 FTS5 全文索引迁移 ----


def test_fts_migration_fresh_db(conn):
    """新库到 user_version=9，FTS 表与三个同步触发器都在。"""
    assert _user_version(conn) == 9
    names = {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='trigger' "
            "AND name LIKE 'messages_fts_%'"
        )
    }
    assert names == {"messages_fts_ai", "messages_fts_au", "messages_fts_ad"}
    assert conn.execute(
        "SELECT 1 FROM sqlite_master WHERE name='messages_fts'"
    ).fetchone() is not None


def test_fts_triggers_keep_index_synced(conn):
    conn.execute(
        "INSERT INTO messages (source_chat_id, source_message_id, original_text) "
        "VALUES (-1001, 1, '游戏机攻略分享')"
    )
    assert conn.execute(
        "SELECT rowid FROM messages_fts WHERE messages_fts MATCH '游戏机'"
    ).fetchone() is not None
    conn.execute("UPDATE messages SET original_text='旅行日记分享' WHERE rowid=1")
    assert conn.execute(
        "SELECT rowid FROM messages_fts WHERE messages_fts MATCH '\"旅行日\"'"
    ).fetchone() is not None
    assert conn.execute(
        "SELECT rowid FROM messages_fts WHERE messages_fts MATCH '游戏机'"
    ).fetchone() is None
    conn.execute("DELETE FROM messages WHERE rowid=1")
    assert conn.execute("SELECT COUNT(*) FROM messages_fts").fetchone()[0] == 0


def test_fts_migration_populates_existing_rows(tmp_path):
    """0008 时代的旧库升级后，存量行已在索引里，搜索能查到。"""
    import shutil

    legacy_dir = tmp_path / "legacy"
    legacy_dir.mkdir()
    for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
        if _version_num(path.stem) <= 8:
            shutil.copy(path, legacy_dir / path.name)
    db = open_db(tmp_path / "legacy.sqlite")
    apply_migrations(db, legacy_dir)
    assert _user_version(db) == 8
    db.execute(
        "INSERT INTO messages (source_chat_id, source_message_id, original_text) "
        "VALUES (-1001, 1, '旧库存的游戏机攻略')"
    )
    db.commit()

    apply_migrations(db)  # 升级到 0009，rebuild 为存量行建索引
    assert _user_version(db) == 9
    assert db.execute(
        "SELECT rowid FROM messages_fts WHERE messages_fts MATCH '游戏机'"
    ).fetchone() is not None
