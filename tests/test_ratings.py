"""Rating 数据操作：定位、更新与重渲染。"""

from __future__ import annotations

import sqlite3

import pytest

from app.database.migrate import apply_migrations, open_db
from app.processor.ratings import find_message_by_target, update_rating
from app.renderer.db import render_from_db


@pytest.fixture
def conn(tmp_path) -> sqlite3.Connection:
    c = open_db(tmp_path / "r.sqlite")
    apply_migrations(c)
    return c


def _seed(conn, rating: int = 0) -> None:
    conn.execute(
        "INSERT INTO messages (id, source_chat_id, source_message_id, "
        "target_chat_id, target_message_id, original_text, source_url, rating) "
        "VALUES (1, -1001, 1, -1002, 10, '正文', 'https://t.me/x/1', ?)",
        (rating,),
    )
    conn.execute("INSERT INTO tags (id, name, normalized_name) VALUES (1, '游戏', '游戏')")
    conn.execute("INSERT INTO message_tags (message_id, tag_id, type) VALUES (1, 1, 'source')")
    conn.commit()


def test_find_message_by_target_hit(conn):
    _seed(conn)
    assert find_message_by_target(conn, -1002, 10)["id"] == 1


def test_find_message_by_target_miss(conn):
    _seed(conn)
    assert find_message_by_target(conn, -1002, 999) is None


def test_update_rating_rerenders(conn):
    _seed(conn)
    rendered = update_rating(conn, 1, 5)
    assert rendered == (
        "推荐指数：⭐⭐⭐⭐⭐\n#游戏\n\n正文\n\n来自：\nhttps://t.me/x/1"
    )
    row = conn.execute("SELECT * FROM messages WHERE id=1").fetchone()
    assert row["rating"] == 5
    assert row["rendered_text"] == rendered


def test_update_rating_zero_clears(conn):
    _seed(conn, rating=4)
    rendered = update_rating(conn, 1, 0)
    assert rendered == "#游戏\n\n正文\n\n来自：\nhttps://t.me/x/1"
    assert conn.execute("SELECT rating FROM messages WHERE id=1").fetchone()["rating"] == 0


def test_update_rating_missing_message(conn):
    assert update_rating(conn, 999, 5) is None


def test_render_from_db_omits_empty_sections(conn):
    conn.execute(
        "INSERT INTO messages (id, source_chat_id, source_message_id, original_text) "
        "VALUES (2, -1001, 2, '纯文本')"
    )
    conn.commit()
    row = conn.execute("SELECT * FROM messages WHERE id=2").fetchone()
    assert render_from_db(conn, row) == "纯文本"


def test_render_from_db_body_override(conn):
    _seed(conn)
    row = conn.execute("SELECT * FROM messages WHERE id=1").fetchone()
    rendered = render_from_db(conn, row, body_override="相册锚文字")
    assert rendered == "#游戏\n\n相册锚文字\n\n来自：\nhttps://t.me/x/1"
