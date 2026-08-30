"""统一消息适配：把 Telethon Message 提成可落库的规范字段。

消息结构差异（文本/图片/视频/文件/相册/语音）在此收敛，
避免下游为每种媒体写重复逻辑（文档第 34 节）。
"""

from __future__ import annotations

from dataclasses import dataclass

from telethon.tl.types import (
    DocumentAttributeAudio,
    DocumentAttributeSticker,
    DocumentAttributeVideo,
    MessageMediaDocument,
    MessageMediaPhoto,
)


@dataclass(frozen=True)
class IncomingMessage:
    source_chat_id: int
    source_message_id: int
    text: str
    media_type: str | None
    media_group_id: str | None
    source_url: str | None


def classify_media(media) -> str | None:
    """返回 media 类型：photo/video/document/audio/voice/sticker/other；无媒体返回 None。"""
    if media is None:
        return None
    if isinstance(media, MessageMediaPhoto):
        return "photo"
    if isinstance(media, MessageMediaDocument):
        doc = media.document
        for attr in doc.attributes:
            if isinstance(attr, DocumentAttributeSticker):
                return "sticker"
            if isinstance(attr, DocumentAttributeVideo):
                return "video"
            if isinstance(attr, DocumentAttributeAudio):
                return "voice" if attr.voice else "audio"
        return "document"
    return "other"


def build_source_url(chat_entity, message_id: int) -> str | None:
    """公开频道生成 t.me/<username>/<id>；无 username（私有/群）返回 None。"""
    username = getattr(chat_entity, "username", None)
    return f"https://t.me/{username}/{message_id}" if username else None


def build_incoming(message, chat_id: int, source_url: str | None) -> IncomingMessage:
    return IncomingMessage(
        source_chat_id=chat_id,
        source_message_id=message.id,
        text=message.message or "",
        media_type=classify_media(message.media),
        media_group_id=message.grouped_id,
        source_url=source_url,
    )
