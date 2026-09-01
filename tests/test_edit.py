"""编辑共享层：tag/rating 变更 → DB 重渲染 → edit 目标消息 → 刷新索引。

verify 双向同步的唯一入口（Telegram 命令与 Web API 均走这里）。
"""

from __future__ import annotations

from types import SimpleNamespace

from app.database.migrate import apply_migrations, open_db
from app.processor.adapter import build_incoming
from app.processor.edit import apply_message_edit
from app.processor.recorder import record_message


def _setup(tmp_path, chat_id=-1001):
    conn = open_db(tmp_path / "e.sqlite")
    apply_migrations(conn)
    msg = _incoming(chat_id=chat_id, tags_text="正文")
    mid = record_message(
        conn, build_incoming(msg, chat_id, None), source_tags=[], preserve_original=False
    )
    # 模拟已归档：设目标 + 重渲染
    conn.execute(
        "UPDATE messages SET status='archived', target_chat_id=-1005, "
        "target_message_id=99, rendered_text='正文' WHERE id=?",
        (mid,),
    )
    conn.commit()
    return conn, mid


def _incoming(chat_id=-1001, mid=7, tags_text="正文"):
    return SimpleNamespace(id=mid, message=tags_text, media=None, grouped_id=None)


class _FakeClient:
    """记录 edit_message 调用的假客户端。"""

    def __init__(self):
        self.edits = []

    async def edit_message(self, chat_id, message_id, text):
        self.edits.append((chat_id, message_id, text))


def test_apply_rating_edits_target(tmp_path):
    conn, mid = _setup(tmp_path)
    client = _FakeClient()
    assert asyncio_run(apply_message_edit(client, conn, mid, rating=4))
    row = conn.execute("SELECT rating, rendered_text FROM messages WHERE id=?", (mid,)).fetchone()
    assert row["rating"] == 4
    assert client.edits == [(-1005, 99, row["rendered_text"])]


def test_apply_add_tags_and_indexer(tmp_path):
    conn, mid = _setup(tmp_path)
    client = _FakeClient()
    calls = {"n": 0}

    class Indexer:
        def schedule(self):
            calls["n"] += 1

    assert asyncio_run(
        apply_message_edit(client, conn, mid, add_tags=["游戏", "MOD"], indexer=Indexer())
    )
    tags = {
        r["name"] for r in conn.execute(
            "SELECT t.name FROM message_tags mt JOIN tags t ON t.id=mt.tag_id "
            "WHERE mt.message_id=?", (mid,)
        )
    }
    assert tags == {"游戏", "MOD"}
    assert calls["n"] == 1
    assert len(client.edits) == 1


def test_apply_remove_tags(tmp_path):
    conn, mid = _setup(tmp_path)
    client = _FakeClient()
    asyncio_run(
        apply_message_edit(client, conn, mid, add_tags=["保留", "删除"], indexer=None)
    )
    client.edits.clear()
    assert asyncio_run(
        apply_message_edit(client, conn, mid, remove_tag_names=["删除"])
    )
    tags = {
        r["name"] for r in conn.execute(
            "SELECT t.name FROM message_tags mt JOIN tags t ON t.id=mt.tag_id "
            "WHERE mt.message_id=?", (mid,)
        )
    }
    assert tags == {"保留"}


def test_apply_nonexistent_message_returns_false(tmp_path):
    conn, mid = _setup(tmp_path)
    client = _FakeClient()
    assert asyncio_run(apply_message_edit(client, conn, 99999, rating=3)) is False
    assert client.edits == []


def test_apply_no_action_returns_false(tmp_path):
    conn, mid = _setup(tmp_path)
    client = _FakeClient()
    assert asyncio_run(apply_message_edit(client, conn, mid)) is False
    assert client.edits == []



def asyncio_run(coro):
    import asyncio

    return asyncio.run(coro)


def _setup_target(tmp_path):
    conn, mid = _setup(tmp_path)
    conn.execute(
        "INSERT INTO message_targets "
        "(id, message_id, target_chat_id, target_message_id, status, original_text, "
        "original_html, rendered_text, rating) "
        "VALUES (1, ?, -1005, 99, 'archived', '正文', '<b>正文</b>', '<b>正文</b>', 0)",
        (mid,),
    )
    conn.commit()
    return conn, mid


def test_target_rating_preserves_existing_html_body(tmp_path):
    conn, mid = _setup_target(tmp_path)
    client = _FakeClient()
    assert asyncio_run(apply_message_edit(client, conn, mid, target_id=1, rating=4))
    target = conn.execute(
        "SELECT original_text, original_html, rendered_text FROM message_targets WHERE id=1"
    ).fetchone()
    assert target["original_text"] == "正文"
    assert target["original_html"] == "<b>正文</b>"
    assert "<b>正文</b>" in target["rendered_text"]
    assert "<b>正文</b>" in client.edits[0][2]
