"""多目标归档复制与目标映射。"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from telethon.tl.types import MessageMediaPhoto, Photo, PhotoCachedSize

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
    database_path = "copier.sqlite"

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


def _photo_media() -> MessageMediaPhoto:
    photo = Photo(
        id=1,
        access_hash=2,
        file_reference=b"\x01",
        date=None,
        sizes=[PhotoCachedSize(type="s", w=100, h=100, bytes=b"\xff\xd8\xff")],
        dc_id=1,
    )
    return MessageMediaPhoto(photo=photo)


class ThumbClient(FakeClient):
    """带图片媒体与落盘 download_media 的假客户端，用于缩略图键断言。"""

    async def get_messages(self, chat, ids):
        return SimpleNamespace(id=ids, message="图", media=_photo_media(), grouped_id=None)

    async def send_file(self, target, file, caption, parse_mode):
        sent = []
        for _ in file:
            message = SimpleNamespace(id=self.next_message_id)
            self.next_message_id += 1
            sent.append(message)
        self.sent.append((target.id, sent[0].id))
        return sent

    async def download_media(self, message, file=None, thumb=None):
        Path(file).write_bytes(b"\xff\xd8\xff")
        return file


@pytest.mark.asyncio
async def test_archive_thumb_key_is_source_media_identity(conn, tmp_path):
    """缩略图键 = 源群 chat_id + 媒体消息 id，与目标频道/数据库 id 无关。"""
    config = Config()
    config.database_path = str(tmp_path / "copier.sqlite")
    client = ThumbClient()

    await archive_message_by_db_id(client, config, conn, 1)

    expected_name = "-1001_7.jpg"  # source_chat_id=-1001, 媒体消息 id=7
    row = conn.execute("SELECT thumb_path FROM messages WHERE id=1").fetchone()
    assert Path(row["thumb_path"]).name == expected_name
    assert Path(row["thumb_path"]).exists()
    targets = conn.execute(
        "SELECT target_chat_id, thumb_path FROM message_targets ORDER BY target_chat_id"
    ).fetchall()
    assert {t["thumb_path"] for t in targets} == {row["thumb_path"]}


@pytest.mark.asyncio
async def test_archive_retry_keeps_existing_thumb_path(conn, tmp_path):
    """重试时缩略图抓取失败不得抹掉已有的 thumb_path。"""
    config = Config()
    config.database_path = str(tmp_path / "copier.sqlite")
    await archive_message_by_db_id(ThumbClient(), config, conn, 1)

    class NoDownloadClient(ThumbClient):
        async def download_media(self, message, file=None, thumb=None):
            raise OSError("network down")

    conn.execute(
        "UPDATE message_targets SET status='pending' WHERE target_chat_id=-1003"
    )
    conn.commit()
    await archive_message_by_db_id(NoDownloadClient(), config, conn, 1)

    row = conn.execute(
        "SELECT thumb_path FROM message_targets WHERE target_chat_id=-1003"
    ).fetchone()
    assert Path(row["thumb_path"]).name == "-1001_7.jpg"


class AlbumClient(ThumbClient):
    """相册场景假客户端：按 ids 批量返回组员，记录每次 send_file 的媒体数。"""

    def __init__(self):
        super().__init__()
        self.album_sizes: list[int] = []
        self.scanned = False

    async def get_messages(self, chat, ids=None, limit=None):
        if ids is not None:
            if isinstance(ids, int):
                return SimpleNamespace(
                    id=ids, message="图", media=_photo_media(), grouped_id="grp1"
                )
            return [
                SimpleNamespace(id=i, message="图", media=_photo_media(), grouped_id="grp1")
                for i in sorted(ids)
            ]
        self.scanned = True
        return []

    async def send_file(self, target, file, caption, parse_mode):
        self.album_sizes.append(len(file))
        return await super().send_file(target, file, caption, parse_mode)


@pytest.mark.asyncio
async def test_album_collected_from_db_members(conn, tmp_path, monkeypatch):
    """相册按落库成员精确取组：队列积压/窗口外不再依赖扫描。"""
    from app.telegram import copier

    monkeypatch.setattr(copier, "_SETTLE_QUIET", 0)
    monkeypatch.setattr(copier, "_SETTLE_MAX", 0)

    conn.execute("UPDATE messages SET media_group_id='grp1' WHERE id=1")
    conn.executemany(
        "INSERT INTO media_group_members (source_chat_id, grouped_id, source_message_id) "
        "VALUES (-1001, 'grp1', ?)",
        [(5,), (6,), (7,)],
    )
    conn.commit()
    config = Config()
    config.database_path = str(tmp_path / "copier.sqlite")
    client = AlbumClient()

    await archive_message_by_db_id(client, config, conn, 1)

    assert client.album_sizes == [3, 3]  # 每个目标频道都是整组 3 条
    assert not client.scanned


@pytest.mark.asyncio
async def test_album_falls_back_to_scan_without_members(conn, tmp_path, monkeypatch):
    """旧数据无成员记录时回退扫描最近消息（v1 行为）。"""
    from app.telegram import copier

    monkeypatch.setattr(copier, "_SETTLE_QUIET", 0)
    monkeypatch.setattr(copier, "_SETTLE_MAX", 0)

    conn.execute("UPDATE messages SET media_group_id='grp1' WHERE id=1")
    conn.commit()
    config = Config()
    config.database_path = str(tmp_path / "copier.sqlite")

    class ScanClient(AlbumClient):
        async def get_messages(self, chat, ids=None, limit=None):
            if ids is not None:
                return SimpleNamespace(
                    id=ids, message="图", media=_photo_media(), grouped_id="grp1"
                )
            self.scanned = True
            return [
                SimpleNamespace(id=i, message="图", media=_photo_media(), grouped_id="grp1")
                for i in (5, 6, 7)
            ]

    client = ScanClient()
    await archive_message_by_db_id(client, config, conn, 1)

    assert client.scanned
    assert client.album_sizes == [3, 3]
