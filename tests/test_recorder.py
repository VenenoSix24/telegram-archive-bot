"""记录器：落库、Tag 合并、去重。"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.database.migrate import apply_migrations, open_db
from app.processor.adapter import build_incoming
from app.processor.recorder import add_manual_tags, record_message


@pytest.fixture
def conn(tmp_path):
    c = open_db(tmp_path / "r.sqlite")
    apply_migrations(c)
    return c


def _msg(text="正文", mid=7, grouped_id=None):
    return SimpleNamespace(id=mid, message=text, media=None, grouped_id=grouped_id)


def _tags(conn, message_id):
    return conn.execute(
        "SELECT t.name, mt.type FROM message_tags mt "
        "JOIN tags t ON t.id = mt.tag_id "
        "WHERE mt.message_id=? ORDER BY mt.rowid",
        (message_id,),
    ).fetchall()


def _record(conn, message, source_tags=("游戏",), preserve_original=True, manual=()):
    inc = build_incoming(message, -1001, None)
    return record_message(
        conn,
        inc,
        source_tags=list(source_tags),
        preserve_original=preserve_original,
        manual_tags=list(manual),
    )


def test_record_saves_message_and_source_tag(conn):
    mid = _record(conn, _msg(text="GTA5 教程"))
    assert mid == 1
    row = conn.execute("SELECT * FROM messages WHERE id=1").fetchone()
    assert row["source_chat_id"] == -1001
    assert row["source_message_id"] == 7
    assert row["status"] == "new"
    assert row["media_type"] == "text"
    assert [(t["name"], t["type"]) for t in _tags(conn, 1)] == [("游戏", "source")]


def test_record_saves_template_snapshot(conn):
    mid = record_message(
        conn,
        build_incoming(_msg(), -1001, None),
        source_tags=[],
        preserve_original=False,
        template_layout=["body", "tags"],
    )
    row = conn.execute("SELECT template_layout FROM messages WHERE id=?", (mid,)).fetchone()
    assert row["template_layout"] == '["body", "tags"]'


def test_record_preserves_original_hashtags(conn):
    mid = _record(conn, _msg(text="#GTA5 教程"))
    assert [(t["name"], t["type"]) for t in _tags(conn, mid)] == [
        ("游戏", "source"),
        ("GTA5", "original"),
    ]


def test_record_dedupes_source(conn):
    first = _record(conn, _msg(text="#GTA5 教程"))
    second = _record(conn, _msg(text="#GTA5 教程"))
    assert first == 1
    assert second is None


def test_record_manual_overrides_type(conn):
    mid = _record(conn, _msg(text="正文"), manual=["游戏"])
    assert [(t["name"], t["type"]) for t in _tags(conn, mid)] == [("游戏", "manual")]


def test_record_preserve_original_false(conn):
    mid = _record(conn, _msg(text="#GTA5 教程"), preserve_original=False)
    assert [(t["name"], t["type"]) for t in _tags(conn, mid)] == [("游戏", "source")]


def test_record_merge_order(conn):
    mid = _record(
        conn,
        _msg(text="#GTA5 教程"),
        source_tags=("游戏", "GTA5"),
        manual=["MOD"],
    )
    assert [(t["name"], t["type"]) for t in _tags(conn, mid)] == [
        ("游戏", "source"),
        ("GTA5", "original"),
        ("MOD", "manual"),
    ]


def test_record_album_group_dedupes(conn):
    first = _record(conn, _msg(text="相册文字", grouped_id="grp1"))
    second = _record(conn, _msg(text="同组其他", grouped_id="grp1", mid=8))
    assert first == 1
    assert second is None


def test_add_manual_tags_merges_and_keeps_types(conn):
    mid = _record(conn, _msg(text="#GTA5 教程"))
    rendered = add_manual_tags(conn, mid, ["MOD", "游戏"])
    assert [(t["name"], t["type"]) for t in _tags(conn, mid)] == [
        ("游戏", "source"),
        ("GTA5", "original"),
        ("MOD", "manual"),
    ]
    assert "MOD" in rendered
    saved = conn.execute("SELECT rendered_text FROM messages WHERE id=1").fetchone()
    assert saved["rendered_text"] == rendered


def test_add_manual_tags_missing_message(conn):
    assert add_manual_tags(conn, 999, ["MOD"]) is None
