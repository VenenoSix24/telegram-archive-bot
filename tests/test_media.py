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


class _FakeClient:
    """download_media 落盘假客户端：给文件写内存空 JPEG 字节。"""

    async def download_media(self, message, file=None, thumb=None):
        Path(file).write_bytes(b"\xff\xd8\xff")
        return file


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


def test_backfill_updates_thumb_path_only_media(conn, tmp_path):
    conn.execute(
        "INSERT INTO messages (source_chat_id, source_message_id, media_type, "
        "status) VALUES (-1, 1, 'photo', 'archived'), (-1, 2, 'text', 'archived')"
    )
    conn.commit()

    media = _photo_media()

    class Client:
        async def get_entity(self, chat):
            return None

        async def get_messages(self, chat, ids=None):
            return _message(media, mid=ids)

        async def download_media(self, message, file=None, thumb=None):
            Path(file).write_bytes(b"\xff\xd8\xff")
            return file

    cache = ThumbnailCache(Path(tmp_path) / "thumbs")
    cfg = SimpleNamespace(forward_interval=0.0)
    count = asyncio.run(backfill_thumbs(Client(), cfg, conn, cache, limit=10))
    assert count == 1  # 只有 photo 补抓，text 不补
    row = conn.execute("SELECT thumb_path FROM messages WHERE id=1").fetchone()
    assert row["thumb_path"] and "1" in row["thumb_path"]
