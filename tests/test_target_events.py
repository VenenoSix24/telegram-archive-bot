"""目标频道事件 handler：Telegram 侧编辑/删除写回对应副本。

覆盖交接文档已知缺口：MessageEdited / MessageDeleted 此前零测试，
sync_target_edits 语义 bug 因此长期存活。
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.database.migrate import apply_migrations, open_db
from app.processor.handlers import (
    attach_reply_command_handler,
    attach_target_delete_handler,
    attach_target_edit_handler,
)


@pytest.fixture
def conn(tmp_path):
    connection = open_db(tmp_path / "targets.sqlite")
    apply_migrations(connection)
    connection.execute(
        "INSERT INTO messages (id, source_chat_id, source_message_id, media_type, "
        "original_text, target_chat_id, target_message_id, status) "
        "VALUES (1, -1001, 7, 'text', '原始正文', -1002, 100, 'archived')"
    )
    connection.execute(
        "INSERT INTO message_targets (message_id, target_chat_id, target_message_id, "
        "original_text, original_html, rendered_text, rating, status) "
        "VALUES (1, -1002, 100, '频道A正文', '', '频道A正文', 0, 'archived')"
    )
    connection.execute(
        "INSERT INTO message_targets (message_id, target_chat_id, target_message_id, "
        "original_text, original_html, rendered_text, rating, status) "
        "VALUES (1, -1003, 200, '频道B正文', '', '频道B正文', 0, 'archived')"
    )
    connection.commit()
    return connection


class FakeClient:
    def __init__(self):
        self.edits: list[tuple[int, int, str]] = []
        self.deleted: list[tuple[int, list[int]]] = []
        self.handlers: dict = {}

    def on(self, event):
        def decorator(func):
            self.handlers[event] = func
            return func

        return decorator

    async def edit_message(self, chat_id, message_id, text, parse_mode=None):
        self.edits.append((chat_id, message_id, text))

    async def delete_messages(self, chat_id, ids):
        self.deleted.append((chat_id, ids))


class Config:
    def all_target_channel_ids(self):
        return {-1002, -1003}


def _edited_event(chat_id: int, message_id: int, text: str):
    return SimpleNamespace(
        chat_id=chat_id,
        message=SimpleNamespace(id=message_id, message=text, entities=[]),
    )


def _deleted_event(chat_id: int, message_ids: list[int]):
    return SimpleNamespace(chat_id=chat_id, deleted_ids=message_ids)


@pytest.mark.asyncio
async def test_target_edited_syncs_only_edited_copy(conn):
    client = FakeClient()
    handler = attach_target_edit_handler(client, Config(), conn)

    await handler(_edited_event(-1002, 100, "TG 改过的新正文"))

    assert len(client.edits) == 1
    assert client.edits[0][:2] == (-1002, 100)
    assert "TG 改过的新正文" in client.edits[0][2]
    edited = conn.execute(
        "SELECT original_text, status FROM message_targets WHERE target_chat_id=-1002"
    ).fetchone()
    sibling = conn.execute(
        "SELECT original_text, rendered_text FROM message_targets WHERE target_chat_id=-1003"
    ).fetchone()
    assert edited["original_text"] == "TG 改过的新正文"
    assert sibling["original_text"] == "频道B正文"
    assert "频道B正文" in sibling["rendered_text"]


@pytest.mark.asyncio
async def test_target_edited_ignores_unknown_messages(conn):
    client = FakeClient()
    handler = attach_target_edit_handler(client, Config(), conn)

    await handler(_edited_event(-1002, 999, "不是归档消息"))
    await handler(_edited_event(-1009, 100, "不在监听的频道"))

    assert client.edits == []
    assert conn.execute(
        "SELECT COUNT(*) AS n FROM message_targets WHERE original_text='TG 改过的新正文'"
    ).fetchone()["n"] == 0


@pytest.mark.asyncio
async def test_target_edited_extracts_body_not_skeleton(conn):
    """回归：TG 编辑整条渲染消息时只回写正文，不把评级/Tag/来源套进正文。"""
    conn.execute("UPDATE messages SET source_url='https://t.me/src/7' WHERE id=1")
    conn.execute("UPDATE message_targets SET rating=4 WHERE target_chat_id=-1002")
    conn.execute(
        "INSERT INTO tags (name, normalized_name) VALUES ('游戏', '游戏'), ('MOD', 'mod')"
    )
    conn.execute(
        "INSERT INTO target_tags (target_id, tag_id, type) "
        "SELECT mt.id, t.id, 'manual' FROM message_targets mt, tags t "
        "WHERE mt.target_chat_id=-1002 AND t.name='游戏'"
    )
    conn.execute(
        "INSERT INTO target_tags (target_id, tag_id, type) "
        "SELECT mt.id, t.id, 'manual' FROM message_targets mt, tags t "
        "WHERE mt.target_chat_id=-1002 AND t.name='MOD'"
    )
    conn.commit()
    client = FakeClient()
    handler = attach_target_edit_handler(client, Config(), conn)

    rendered = (
        "推荐指数：⭐⭐⭐⭐\n\n#游戏 #MOD\n\nTG 里的新正文\n\n"
        "来自：\nhttps://t.me/src/7"
    )
    await handler(_edited_event(-1002, 100, rendered))

    target = conn.execute(
        "SELECT original_text, rendered_text FROM message_targets WHERE target_chat_id=-1002"
    ).fetchone()
    assert target["original_text"] == "TG 里的新正文"
    assert target["rendered_text"].count("推荐指数") == 1
    assert target["rendered_text"].count("来自：") == 1
    sibling = conn.execute(
        "SELECT original_text FROM message_targets WHERE target_chat_id=-1003"
    ).fetchone()
    assert sibling["original_text"] == "频道B正文"


@pytest.mark.asyncio
async def test_target_deleted_marks_tombstone_without_sibling_changes(conn):
    client = FakeClient()
    handler = attach_target_delete_handler(client, Config(), conn)

    await handler(_deleted_event(-1002, [100]))

    status_a = conn.execute(
        "SELECT status FROM message_targets WHERE target_chat_id=-1002"
    ).fetchone()["status"]
    status_b = conn.execute(
        "SELECT status FROM message_targets WHERE target_chat_id=-1003"
    ).fetchone()["status"]
    assert status_a == "deleted"
    assert status_b == "archived"


class ReplyConfig:
    source_chats = [SimpleNamespace(chat_id=-1001)]
    admins = {555}
    rating_enabled = True

    def all_target_channel_ids(self):
        return {-1002, -1003}


def _reply_event(chat_id: int, reply_to: int, text: str, sender_id: int = 555):
    return SimpleNamespace(
        chat_id=chat_id,
        sender_id=sender_id,
        message=SimpleNamespace(id=99, reply_to_msg_id=reply_to, text=text),
    )


@pytest.mark.asyncio
async def test_source_reply_rating_updates_all_copies(conn):
    """源群回复 /rating 作用于共享源 → 更新该源消息的全部目标副本。"""
    client = FakeClient()
    attach_reply_command_handler(client, ReplyConfig(), conn)

    source_handler = next(
        func
        for event, func in client.handlers.items()
        if event.__class__.__name__ == "NewMessage" and -1001 in event.chats
    )
    await source_handler(_reply_event(-1001, 7, "/rating 4"))

    ratings = {
        row["target_chat_id"]: row["rating"]
        for row in conn.execute(
            "SELECT target_chat_id, rating FROM message_targets WHERE message_id=1"
        )
    }
    assert ratings == {-1002: 4, -1003: 4}
    assert {(chat, mid) for chat, mid, _ in client.edits} == {(-1002, 100), (-1003, 200)}
    assert client.deleted == [(-1001, [99])]


@pytest.mark.asyncio
async def test_target_reply_tag_updates_only_that_copy(conn):
    """目标频道回复 /tag 只作用于被回复的那条副本。"""
    client = FakeClient()
    attach_reply_command_handler(client, ReplyConfig(), conn)

    target_handler = next(
        func
        for event, func in client.handlers.items()
        if event.__class__.__name__ == "NewMessage" and -1003 in event.chats
    )
    await target_handler(_reply_event(-1003, 200, "/tag MOD 画质"))

    tags_a = conn.execute(
        "SELECT t.name FROM target_tags tt JOIN tags t ON t.id=tt.tag_id "
        "JOIN message_targets mt ON mt.id=tt.target_id WHERE mt.target_chat_id=-1002"
    ).fetchall()
    tags_b = conn.execute(
        "SELECT t.name FROM target_tags tt JOIN tags t ON t.id=tt.tag_id "
        "JOIN message_targets mt ON mt.id=tt.target_id WHERE mt.target_chat_id=-1003"
    ).fetchall()
    assert tags_a == []
    assert {r["name"] for r in tags_b} == {"MOD", "画质"}
    assert {(chat, mid) for chat, mid, _ in client.edits} == {(-1003, 200)}


@pytest.mark.asyncio
async def test_source_reply_without_copies_falls_back_to_parent(conn):
    """旧数据没有副本行时回退父级路径，行为与旧版一致。"""
    conn.execute(
        "UPDATE message_targets SET status='deleted' WHERE target_chat_id=-1002"
    )
    conn.execute(
        "UPDATE message_targets SET status='deleted' WHERE target_chat_id=-1003"
    )
    conn.commit()
    client = FakeClient()
    attach_reply_command_handler(client, ReplyConfig(), conn)

    source_handler = next(
        func
        for event, func in client.handlers.items()
        if event.__class__.__name__ == "NewMessage" and -1001 in event.chats
    )
    await source_handler(_reply_event(-1001, 7, "/rating 5"))

    rating = conn.execute("SELECT rating FROM messages WHERE id=1").fetchone()["rating"]
    assert rating == 5
    assert client.deleted == [(-1001, [99])]


@pytest.mark.asyncio
async def test_reply_command_ignores_non_admin(conn):
    client = FakeClient()
    attach_reply_command_handler(client, ReplyConfig(), conn)

    source_handler = next(
        func
        for event, func in client.handlers.items()
        if event.__class__.__name__ == "NewMessage" and -1001 in event.chats
    )
    await source_handler(_reply_event(-1001, 7, "/rating 4", sender_id=111))

    assert client.edits == []
    assert client.deleted == []
