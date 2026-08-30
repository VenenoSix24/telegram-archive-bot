"""数据库 schema、迁移幂等与唯一约束。"""

from __future__ import annotations

import sqlite3

import pytest

from app.database.migrate import apply_migrations, open_db


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
