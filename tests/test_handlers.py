"""新消息事件处理：指令过滤、落库、入队。"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.config import Config, SourceChat
from app.database.migrate import apply_migrations, open_db
from app.processor.adapter import IncomingMessage
from app.processor.handlers import process_incoming
from app.queue.manager import QueueManager


async def _ok(mid):
    return None


def _config(chat_id: int = -1001) -> Config:
    return Config(
        api_id=1,
        api_hash="x",
        bot_token=None,
        source_chats=[
            SourceChat(chat_id=chat_id, name="源", default_tags=["游戏"]),
            SourceChat(chat_id=-1003, name="中转群", default_tags=["历史"]),
        ],
        target_channel_id=-1002,
        forward_interval=3,
        retry_count=3,
        show_link=True,
        preserve_original=True,
        rating_enabled=True,
        admins=frozenset({1}),
        url_template=None,
        database_path="x.sqlite",
        web_enabled=False,
        web_host="127.0.0.1",
        web_port=8000,
        web_token="",
    )


@pytest.fixture
def ctx(tmp_path):
    conn = open_db(tmp_path / "h.sqlite")
    apply_migrations(conn)
    queue = QueueManager(conn, sender=_ok, interval=0.1, max_retries=3)
    return conn, queue, _config()


def _incoming(text="正文", chat_id=-1001, mid=7):
    return IncomingMessage(
        source_chat_id=chat_id,
        source_message_id=mid,
        text=text,
        media_type=None,
        media_group_id=None,
        source_url=None,
    )


def _pending(conn):
    return conn.execute("SELECT count(*) AS n FROM queue WHERE status='pending'").fetchone()["n"]


def test_normal_message_enqueues(ctx):
    conn, queue, config = ctx
    assert process_incoming(config, conn, queue, _incoming())
    assert _pending(conn) == 1


def test_command_message_skipped(ctx):
    conn, queue, config = ctx
    assert not process_incoming(config, conn, queue, _incoming(text="/tag 游戏"))
    assert _pending(conn) == 0


def test_duplicate_source_skipped(ctx):
    conn, queue, config = ctx
    assert process_incoming(config, conn, queue, _incoming(mid=7))
    assert not process_incoming(config, conn, queue, _incoming(mid=7))
    assert _pending(conn) == 1


def test_album_later_item_skipped(ctx):
    conn, queue, config = ctx
    first = SimpleNamespace(id=7, message="相册", media=None, grouped_id="grp1")
    second = SimpleNamespace(id=8, message="", media=None, grouped_id="grp1")
    from app.processor.adapter import build_incoming

    inc1 = build_incoming(first, -1001, None)
    inc2 = build_incoming(second, -1001, None)
    assert process_incoming(config, conn, queue, inc1)
    assert not process_incoming(config, conn, queue, inc2)
    assert _pending(conn) == 1


def test_relay_message_uses_relay_default_tags(ctx):
    conn, queue, config = ctx
    assert process_incoming(config, conn, queue, _incoming(text="转发历史", chat_id=-1003, mid=9))
    mid = conn.execute(
        "SELECT id FROM messages WHERE source_message_id=9"
    ).fetchone()["id"]
    tags = [
        (r["name"], r["type"])
        for r in conn.execute(
            "SELECT t.name, mt.type FROM message_tags mt "
            "JOIN tags t ON t.id = mt.tag_id WHERE mt.message_id=?",
            (mid,),
        )
    ]
    assert tags == [("历史", "source")]
