"""Tag 统计与索引文本（按归档副本统计）。"""

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
    """三条源消息、四条归档副本：消息1→频道-10/-11，消息2→-10，消息3→-11。"""
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
    conn.executemany(
        "INSERT INTO message_targets (id, message_id, target_chat_id, "
        "target_message_id, status) VALUES (?, ?, ?, ?, 'archived')",
        [(1, 1, -10, 100), (2, 1, -11, 101), (3, 2, -10, 102), (4, 3, -11, 103)],
    )
    conn.executemany(
        "INSERT INTO target_tags (target_id, tag_id, type) VALUES (?, ?, 'source')",
        [(1, 1), (2, 1), (3, 1), (4, 2)],
    )
    conn.commit()


def test_compute_tag_counts_counts_and_sorts(conn):
    _seed(conn)
    # 副本口径：游戏 3 条副本、软件 1 条
    assert compute_tag_counts(conn) == [("游戏", 3), ("软件", 1)]


def test_compute_tag_counts_by_target(conn):
    _seed(conn)
    # -10：副本 1、3（均游戏）；-11：副本 2（游戏）+ 副本 4（软件）
    assert compute_tag_counts(conn, target_chat_id=-10) == [("游戏", 2)]
    assert compute_tag_counts(conn, target_chat_id=-11) == [("游戏", 1), ("软件", 1)]


def test_deleted_copy_not_counted(conn):
    _seed(conn)
    conn.execute("UPDATE message_targets SET status='deleted' WHERE id=2")
    conn.commit()
    assert compute_tag_counts(conn, target_chat_id=-11) == [("软件", 1)]
    assert compute_tag_counts(conn) == [("游戏", 2), ("软件", 1)]


def test_target_level_tag_edit_reflected(conn):
    """Web 端只写 target_tags 的编辑要反映到计数（父表 message_tags 不变）。"""
    _seed(conn)
    conn.execute(
        "INSERT INTO tags (id, name, normalized_name) VALUES (3, '手动', '手动')"
    )
    conn.execute(
        "INSERT INTO target_tags (target_id, tag_id, type) VALUES (4, 3, 'manual')"
    )
    conn.commit()
    # -11：副本 2（游戏）+ 副本 4（软件 + 新增手动）；同计数按名称排序
    assert compute_tag_counts(conn, target_chat_id=-11) == [
        ("手动", 1),
        ("游戏", 1),
        ("软件", 1),
    ]
    assert compute_tag_counts(conn) == [("游戏", 3), ("手动", 1), ("软件", 1)]


def test_format_tag_index(conn):
    _seed(conn)
    text = format_tag_index(compute_tag_counts(conn, target_chat_id=-10))
    assert text == "📚 Tags\n\n#游戏 · 2"


def test_format_tag_index_empty():
    assert format_tag_index([]) == "📚 Tags\n\n（暂无 Tag）"
