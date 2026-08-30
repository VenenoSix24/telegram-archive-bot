"""Tag 统计与索引文本。"""

from __future__ import annotations

import sqlite3

import pytest

from app.database.migrate import apply_migrations, open_db
from app.tags.index import compute_tag_counts, format_tag_index


@pytest.fixture
def conn(tmp_path) -> sqlite3.Connection:
    c = open_db(tmp_path / "t.sqlite")
    apply_migrations(c)
    return c


def _seed(conn) -> None:
    conn.execute(
        "INSERT INTO messages (id, source_chat_id, source_message_id) "
        "VALUES (1, -1001, 1), (2, -1001, 2), (3, -1001, 3)"
    )
    conn.execute(
        "INSERT INTO tags (id, name, normalized_name) "
        "VALUES (1, '游戏', '游戏'), (2, '软件', '软件')"
    )
    conn.executemany(
        "INSERT INTO message_tags (message_id, tag_id, type) VALUES (?, ?, 'source')",
        [(1, 1), (2, 1), (3, 2)],
    )
    conn.commit()


def test_compute_tag_counts_counts_and_sorts(conn):
    _seed(conn)
    assert compute_tag_counts(conn) == [("游戏", 2), ("软件", 1)]


def test_format_tag_index(conn):
    _seed(conn)
    text = format_tag_index(compute_tag_counts(conn))
    assert text == "📚 Tags\n\n#游戏 · 2\n#软件 · 1"


def test_format_tag_index_empty():
    assert format_tag_index([]) == "📚 Tags\n\n（暂无 Tag）"
