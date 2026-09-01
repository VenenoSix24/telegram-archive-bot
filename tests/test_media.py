"""W2 数据扩展：migration 0002、媒体元数据采集、缩略图缓存与补抓。"""

from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace

import pytest
from telethon.tl.types import (
    DocumentAttributeAudio,
    DocumentAttributeFilename,
    DocumentAttributeVideo,
    MessageMediaDocument,
    MessageMediaPhoto,
    Photo,
    PhotoCachedSize,
)

from app.database.migrate import apply_migrations, open_db
from app.media.backfill import backfill_thumbs
from app.media.thumbnails import ThumbnailCache, _pick_photo_thumb
from app.processor.adapter import build_incoming, media_file_meta


@pytest.fixture
def conn(tmp_path):
    c = open_db(tmp_path / "m.sqlite")
    apply_migrations(c)
    return c


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


def _doc_media(attrs) -> MessageMediaDocument:
    return MessageMediaDocument(
        document=SimpleNamespace(size=999, attributes=attrs)
    )


def _message(media, mid=7):
    return SimpleNamespace(id=mid, message="", media=media, grouped_id=None)


def test_migration_adds_media_meta_columns(conn):
    cols = {r[1] for r in conn.execute("PRAGMA table_info(messages)")}
    assert {"thumb_path", "file_name", "file_size", "duration"} <= cols


def test_media_file_meta_none_keys():
    assert media_file_meta(None) == (None, None, None)
    assert media_file_meta(_photo_media()) == (None, None, None)


def test_media_file_meta_document():
    media = _doc_media(
        [
            DocumentAttributeFilename("clip.mp4"),
            DocumentAttributeVideo(duration=95, w=1280, h=720),
        ]
    )
    assert media_file_meta(media) == ("clip.mp4", 999, 95)


def test_media_file_meta_audio_duration():
    media = _doc_media(
        [
            DocumentAttributeFilename("song.mp3"),
            DocumentAttributeAudio(duration=183, voice=False),
        ]
    )
    assert media_file_meta(media) == ("song.mp3", 999, 183)


def test_media_file_meta_voice_keeps_duration():
    media = _doc_media([DocumentAttributeAudio(duration=5, voice=True)])
    assert media_file_meta(media) == (None, 999, 5)


def test_record_persists_file_metadata(conn):
    from app.processor.recorder import record_message

    media = _doc_media([DocumentAttributeFilename("book.pdf")])
    inc = build_incoming(_message(media, mid=9), -1001, None)
    mid = record_message(conn, inc, source_tags=["软件"], preserve_original=False)
    row = conn.execute("SELECT * FROM messages WHERE id=?", (mid,)).fetchone()
    assert row["media_type"] == "document"
    assert row["file_name"] == "book.pdf"
    assert row["file_size"] == 999
    assert row["duration"] is None


def test_thumb_cache_path_for(tmp_path):
    assert ThumbnailCache(Path(tmp_path)).path_for(42).name == "42.jpg"


def test_thumbs_dir_follows_database(tmp_path):
    from app.media.thumbnails import thumbs_dir_for

    assert thumbs_dir_for(tmp_path / "data" / "a.sqlite") == tmp_path / "data" / "thumbs"


class _FakeClient:
    """download_media 落盘假客户端：给文件写内存空 JPEG 字节。"""

    async def download_media(self, message, file=None, thumb=None):
        Path(file).write_bytes(b"\xff\xd8\xff")
        return file


def test_thumb_cache_path_includes_chat_identity(tmp_path):
    cache = ThumbnailCache(Path(tmp_path))
    assert cache.path_for(42, chat_id=-1005).name == "-1005_42.jpg"


def test_thumb_cache_fetch_photo(tmp_path):
    cache = ThumbnailCache(Path(tmp_path))
    msg = _message(_photo_media())
    path = asyncio.run(cache.fetch(_FakeClient(), msg, 42))
    assert path is not None and path.exists()
    assert path.name == "42.jpg"


def test_thumb_cache_fetch_ignores_text(tmp_path):
    cache = ThumbnailCache(Path(tmp_path))
    msg = _message(None)
    assert asyncio.run(cache.fetch(_FakeClient(), msg, 7)) is None


def test_choose_thumbnail_message_first_video_not_first_media():
    from app.media.thumbnails import choose_thumbnail_message

    first = _message(_doc_media([DocumentAttributeFilename("photo.jpg")]), mid=1)
    video = _message(_doc_media([DocumentAttributeVideo(duration=2, w=10, h=10)]), mid=2)
    assert choose_thumbnail_message([first, video], "first_video") is video


def test_choose_thumbnail_message_falls_back_first_media_without_video():
    from app.media.thumbnails import choose_thumbnail_message

    first = _message(_doc_media([DocumentAttributeFilename("one.jpg")]), mid=1)
    second = _message(_doc_media([DocumentAttributeFilename("two.jpg")]), mid=2)
    assert choose_thumbnail_message([first, second], "first_video") is first


def test_pick_photo_thumb_prefers_medium_width():
    from telethon.tl.types import PhotoSize as RealPhotoSize

    sizes = [
        RealPhotoSize(type="s", w=100, h=100, size=100),
        RealPhotoSize(type="m", w=640, h=640, size=1000),
        RealPhotoSize(type="x", w=1280, h=1280, size=5000),
        RealPhotoSize(type="y", w=2560, h=2560, size=9000),
    ]
    picked = _pick_photo_thumb(SimpleNamespace(sizes=sizes))
    assert picked is sizes[1]  # 640 是最小且落在 [480,1280]，不用 2560 全图


def test_pick_photo_thumb_no_mid_falls_back_smallest():
    from telethon.tl.types import PhotoSize as RealPhotoSize

    sizes = [RealPhotoSize(type="s", w=100, h=100, size=100)]
    picked = _pick_photo_thumb(SimpleNamespace(sizes=sizes))
    assert picked is sizes[0]


class _BackfillClient:
    """get_messages 按 ids 返回图片消息、download_media 落盘的假客户端。"""

    async def get_entity(self, chat):
        return None

    async def get_messages(self, chat, ids=None):
        return _message(_photo_media(), mid=ids)

    async def download_media(self, message, file=None, thumb=None):
        Path(file).write_bytes(b"\xff\xd8\xff")
        return file


def test_backfill_updates_thumb_path_only_media(conn, tmp_path):
    conn.execute(
        "INSERT INTO messages (source_chat_id, source_message_id, media_type, "
        "status) VALUES (-1, 1, 'photo', 'archived'), (-1, 2, 'text', 'archived')"
    )
    conn.commit()

    cache = ThumbnailCache(Path(tmp_path) / "thumbs")
    cfg = SimpleNamespace(forward_interval=0.0)
    count = asyncio.run(backfill_thumbs(_BackfillClient(), cfg, conn, cache, limit=10))
    assert count == 1  # 只有 photo 补抓，text 不补
    row = conn.execute("SELECT thumb_path FROM messages WHERE id=1").fetchone()
    # 键 = 源群 chat_id + 媒体消息 id，不用数据库 id
    assert row["thumb_path"].endswith("-1_1.jpg")


def test_backfill_fills_target_thumb_paths(conn, tmp_path):
    """补抓结果要同步写入缺失缩略图的目标副本行。"""
    conn.execute(
        "INSERT INTO messages (source_chat_id, source_message_id, media_type, "
        "status) VALUES (-1, 5, 'photo', 'archived')"
    )
    conn.execute(
        "INSERT INTO message_targets (message_id, target_chat_id, "
        "target_message_id, status) VALUES (1, -1002, 50, 'archived')"
    )
    conn.commit()

    cache = ThumbnailCache(Path(tmp_path) / "thumbs")
    cfg = SimpleNamespace(forward_interval=0.0)
    count = asyncio.run(backfill_thumbs(_BackfillClient(), cfg, conn, cache, limit=10))
    assert count == 1
    paths = conn.execute(
        "SELECT thumb_path FROM message_targets WHERE message_id=1"
    ).fetchall()
    assert {p["thumb_path"] for p in paths} == {str(tmp_path / "thumbs" / "-1_5.jpg")}
