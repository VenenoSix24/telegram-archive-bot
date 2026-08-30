"""Telethon client building and chat-access validation.

会话文件固定为 telegram_archive.session（被 .gitignore 排除）。
单进程约束：整个程序共用同一个 client 实例，禁止多进程访问 session。
"""

from __future__ import annotations

from pathlib import Path

from telethon import TelegramClient

from app.config import Config

SESSION_FILE = "telegram_archive.session"


def build_client(config: Config) -> TelegramClient:
    return TelegramClient(Path(SESSION_FILE), config.api_id, config.api_hash)


async def resolve_chat_name(client: TelegramClient, chat_id: int) -> str:
    """返回 chat_id 对应的实体标题；无法访问时抛出带修复提示的异常。"""
    entity = await client.get_entity(chat_id)
    name = getattr(entity, "title", None) or getattr(entity, "username", None) or str(chat_id)
    return name


async def validate_config_chats(client: TelegramClient, config: Config) -> dict:
    """校验配置中的每个 chat 是否可访问，返回 chat_id → 名称 映射。

    不可访问的 chat 会中断启动并给出具体 chat_id，方便用户在 config.yaml 里修正。
    """
    resolved: dict[int, str] = {}
    ids = {c.chat_id for c in config.source_chats}
    ids.add(config.target_channel_id)
    if config.relay_chat_id:
        ids.add(config.relay_chat_id)

    for chat_id in sorted(ids):
        try:
            resolved[chat_id] = await resolve_chat_name(client, chat_id)
        except Exception as exc:  # telethon.errors.rpcerrorlist.*
            raise RuntimeError(
                f"无法访问 chat_id={chat_id}（{type(exc).__name__}）。"
                "确认小号已加入该群/频道，且 config.yaml 中的 chat_id 正确。"
            ) from exc
    return resolved
