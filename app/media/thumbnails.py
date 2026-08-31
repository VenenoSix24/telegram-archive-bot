"""缩略图本地缓存：归档时从 Telegram 下载小图存本地，供 Web 浏览。

任务书 §49：不建媒体仓库，Telegram 存完整媒体、本地只留缩略图。
照片挑「适配 Web 卡的中间档」而非最小（thumb=0 是 1px stripped 糊图）、
也非最大（thumb=-1 会抓全尺寸原图）；视频/文件用 document 首张 thumb
（本身就是封面小图，源没有就不生成，沿用 V1 已确认的平台限制）。
仅缓存，不参与归档消息本体。
"""

from __future__ import annotations

from pathlib import Path

from telethon.tl.types import (
    DocumentAttributeVideo,
    MessageMediaDocument,
    MessageMediaPhoto,
    PhotoCachedSize,
    PhotoSize,
    PhotoSizeProgressive,
)

THUMB_DIR = Path("thumbs")
_EXT = ".jpg"

# Web 卡片缩略图目标宽度：过小糊、过大等于下载原图
_MIN_W, _MAX_W = 480, 1280
# 候选的实物尺寸类型（stripped/cached 等内联小图一律排除）
_PHOTO_SIZES = (PhotoSize, PhotoSizeProgressive, PhotoCachedSize)


def _pick_photo_thumb(photo):
    """从 photo.sizes 挑一个宽度落在 [_MIN_W, _MAX_W] 的最小档；没有则用最小实图。"""
    candidates = [
        s for s in photo.sizes
        if isinstance(s, _PHOTO_SIZES) and getattr(s, "w", 0) and getattr(s, "h", 0)
    ]
    if not candidates:
        return None
    mid = [s for s in candidates if _MIN_W <= s.w <= _MAX_W]
    return min(mid, key=lambda s: s.w) if mid else min(candidates, key=lambda s: s.w)


def choose_thumbnail_message(messages: list, strategy: str = "first_video"):
    """Choose the album message whose thumbnail should represent the group."""
    if not messages:
        return None
    if strategy == "first_video":
        for message in messages:
            media = getattr(message, "media", None)
            document = getattr(media, "document", None)
            if document and any(isinstance(a, DocumentAttributeVideo) for a in document.attributes):
                return message
    return messages[0]
class ThumbnailCache:
    """缩略图存取。单进程主事件循环触发抓取，Web 经独立连接只读。"""

    def __init__(self, directory: Path = THUMB_DIR) -> None:
        self._dir = directory

    @property
    def directory(self) -> Path:
        return self._dir

    def path_for(self, message_id: int) -> Path:
        return self._dir / f"{message_id}{_EXT}"

    async def fetch(self, client, message, message_id: int) -> Path | None:
        """下载并缓存消息缩略图，返回本地路径；无缩略图/失败返回 None。"""
        media = message.media
        if isinstance(media, MessageMediaPhoto):
            thumb = _pick_photo_thumb(media.photo)
        elif isinstance(media, MessageMediaDocument):
            document = media.document
            thumb = -1 if document.thumbs else None
        else:
            return None
        if thumb is None:
            return None
        self._dir.mkdir(parents=True, exist_ok=True)
        dest = self.path_for(message_id)
        try:
            await client.download_media(message, file=dest, thumb=thumb)
        except Exception:
            return None
        return dest if dest.exists() else None
