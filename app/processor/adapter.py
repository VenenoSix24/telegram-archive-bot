"""统一消息适配：把 Telethon Message 提成可落库的规范字段。

消息结构差异（文本/图片/视频/文件/相册/语音）在此收敛，
避免下游为每种媒体写重复逻辑（文档第 34 节）。
"""

from __future__ import annotations

from dataclasses import dataclass

from telethon.extensions import html
from telethon.tl.types import (
    DocumentAttributeAudio,
    DocumentAttributeFilename,
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
    text_html: str = ""
    file_name: str | None = None
    file_size: int | None = None
    duration: int | None = None


def media_file_meta(media) -> tuple[str | None, int | None, int | None]:
    """从媒体提取 (file_name, file_size, duration)；无文件类媒体返回 (None, None, None)。

    时长对视频/音频/语音都有效，Web 卡片直接展示，不做媒体子类型剔除。
    """
    if not isinstance(media, MessageMediaDocument):
        return None, None, None
    doc = media.document
    file_name = None
    duration = None
    for attr in doc.attributes:
        if isinstance(attr, DocumentAttributeFilename):
            file_name = attr.file_name
        elif isinstance(attr, (DocumentAttributeVideo, DocumentAttributeAudio)):
            duration = attr.duration
    return file_name, doc.size, duration


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
    """生成消息来源链接。

    公开实体用 t.me/<username>/<id>；私有频道/超级群（-100 前缀）用
    t.me/c/<内部id>/<id> 深链；普通群无 username 无法生成，返回 None。
    """
    username = getattr(chat_entity, "username", None)
    if username:
        return f"https://t.me/{username}/{message_id}"
    chat_id = getattr(chat_entity, "id", None)
    if isinstance(chat_id, int) and chat_id < 0:
        internal = str(chat_id).removeprefix("-100")
        return f"https://t.me/c/{internal}/{message_id}"
    return None


async def resolve_source_url(client, message, chat_entity, *, show_link: bool = True) -> str | None:
    """归档来源：优先溯转发链的原始消息，退回消息所在群自身。

    从频道转发到分类群的帖子，来源显示原频道帖子链接（溯源）；
    无转发、非频道帖子、或无法访问原始频道时，退回分类群消息链接。
    """
    if not show_link:
        return None
    fwd = getattr(message, "forward", None)
    if fwd is not None:
        peer = getattr(fwd, "from_id", None)
        channel_id = getattr(peer, "channel_id", None)
        post_id = getattr(fwd, "channel_post", None)
        if channel_id and post_id:
            try:
                original = await client.get_entity(peer)
            except Exception:
                original = None
            if original is not None:
                return build_source_url(original, post_id)
    return build_source_url(chat_entity, message.id)


def build_incoming(message, chat_id: int, source_url: str | None) -> IncomingMessage:
    file_name, file_size, duration = media_file_meta(message.media)
    entities = getattr(message, "entities", None) or []
    return IncomingMessage(
        source_chat_id=chat_id,
        source_message_id=message.id,
        text=message.message or "",
        text_html=html.unparse(message.message or "", entities) if entities else "",
        media_type=classify_media(message.media),
        media_group_id=message.grouped_id,
        source_url=source_url,
        file_name=file_name,
        file_size=file_size,
        duration=duration,
    )
