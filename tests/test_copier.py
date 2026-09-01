"""多目标归档复制与目标映射。"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.database.migrate import apply_migrations, open_db
from app.telegram.copier import archive_message_by_db_id


@pytest.fixture
def conn(tmp_path):
    connection = open_db(tmp_path / "copier.sqlite")
    apply_migrations(connection)
    connection.execute(
        "INSERT INTO messages (source_chat_id, source_message_id, media_type, "
        "original_text, status) VALUES (?, ?, 'text', ?, 'new')",
        (-1001, 7, "正文"),
    )
    connection.commit()
    return connection


class FakeClient:
    def __init__(self):
        self.sent: list[tuple[int, int]] = []
        self.next_message_id = 100

    async def get_entity(self, chat_id):
        return SimpleNamespace(id=chat_id, username=f"target{abs(chat_id)}")

    async def get_messages(self, chat, ids):
        return SimpleNamespace(id=ids, message="正文", media=None, grouped_id=None)

    async def send_message(self, target, text, parse_mode):
        message = SimpleNamespace(id=self.next_message_id)
        self.next_message_id += 1
        self.sent.append((target.id, message.id))
        return message


class Config:
    thumbnail_media = "first_video"

    def targets_for(self, source_chat_id):
        return [-1002, -1003]


@pytest.mark.asyncio
async def test_archive_writes_one_target_row_per_target(conn):
    client = FakeClient()

    first_id = await archive_message_by_db_id(client, Config(), conn, 1)

    assert first_id == 100
    assert client.sent == [(-1002, 100), (-1003, 101)]
    targets = conn.execute(
        "SELECT target_chat_id, target_message_id, status "
        "FROM message_targets WHERE message_id=1 ORDER BY target_chat_id"
    ).fetchall()
    assert {tuple(row) for row in targets} == {
        (-1002, 100, "archived"),
        (-1003, 101, "archived"),
    }
    row = conn.execute(
        "SELECT target_chat_id, target_message_id, status FROM messages WHERE id=1"
    ).fetchone()
    assert tuple(row) == (-1002, 100, "archived")


@pytest.mark.asyncio
async def test_archive_does_not_send_completed_targets_again(conn):
    conn.execute(
        "INSERT INTO message_targets "
        "(message_id, target_chat_id, target_message_id, status) "
        "VALUES (1, -1002, 99, 'archived')"
    )
    conn.commit()
    client = FakeClient()

    await archive_message_by_db_id(client, Config(), conn, 1)

    assert client.sent == [(-1003, 100)]
