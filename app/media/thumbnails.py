"""缩略图本地缓存：归档时从 Telegram 下载小图存本地，供 Web 浏览。

任务书 §49：不建媒体仓库，Telegram 存完整媒体、本地只留缩略图。
图片取最小真实尺寸、视频/文件取 document 首张 thumbs（源没有就不生成，
沿用 V1 已确认的平台限制）；仅缓存，不参与归档消息本体。
"""

from __future__ import annotations

from pathlib import Path

from telethon.tl.types import MessageMediaDocument, MessageMediaPhoto

THUMB_DIR = Path("thumbs")
_EXT = ".jpg"

# 照片用最小真实尺寸（thumb=0），视频/文件取首张缩略图（thumb=-1）。
_THUMB_SELECTOR = {MessageMediaPhoto: 0, MessageMediaDocument: -1}


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
        thumb = _THUMB_SELECTOR.get(type(message.media))
        if thumb is None:
            return None
        self._dir.mkdir(parents=True, exist_ok=True)
        dest = self.path_for(message_id)
        try:
            await client.download_media(message, file=dest, thumb=thumb)
        except Exception:
            return None
        return dest if dest.exists() else None
