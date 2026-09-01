"""Telethon client building and chat-access validation.

session 文件与 config.yaml 同目录（被 .gitignore 排除），不依赖 CWD。
单进程约束：整个程序共用同一个 client 实例，禁止多进程访问 session。
"""

from __future__ import annotations

from pathlib import Path

from telethon import TelegramClient

from app.config import Config

SESSION_NAME = "telegram_archive.session"


def build_client(config: Config) -> TelegramClient:
    session = Path(config.config_path).parent / SESSION_NAME
    return TelegramClient(session, config.api_id, config.api_hash)


async def _resolve_entity(client: TelegramClient, chat_id: int):
    """按配置 id 解析实体；正整数失败时按频道内部 id 的 -100 前缀再试。

    Telethon 把正整数默认当作 user id，而用户可能直接填了私密频道的内部 id
    （正确编码为 -100<内部id>），因此需要兜底重试。
    """
    try:
        return await client.get_entity(chat_id)
    except ValueError:
        if 0 < chat_id < 10**12:
            try:
                candidate = int(f"-100{chat_id}")
            except ValueError:
                pass
            else:
                return await client.get_entity(candidate)
        raise


async def resolve_chat_name(client: TelegramClient, chat_id: int) -> str:
    """返回 chat_id 对应的实体标题；无法访问时抛出带修复提示的异常。"""
    entity = await _resolve_entity(client, chat_id)
    name = getattr(entity, "title", None) or getattr(entity, "username", None) or str(chat_id)
    return name


async def resolve_chat_names(client: TelegramClient, config: Config) -> dict[int, str]:
    ids = {c.chat_id for c in config.source_chats}
    ids.update(config.all_target_channel_ids())
    names: dict[int, str] = {}
    for chat_id in sorted(ids):
        try:
            names[chat_id] = await resolve_chat_name(client, chat_id)
        except Exception:
            names[chat_id] = str(chat_id)
    return names


async def validate_config_chats(client: TelegramClient, config: Config) -> dict:
    """校验配置中的每个 chat 是否可访问，返回 chat_id → 名称 映射。"""
    ids = {c.chat_id for c in config.source_chats}
    ids.update(config.all_target_channel_ids())
    resolved: dict[int, str] = {}

    for chat_id in sorted(ids):
        try:
            resolved[chat_id] = await resolve_chat_name(client, chat_id)
        except Exception as exc:  # telethon.errors.rpcerrorlist.*
            raise RuntimeError(
                f"无法访问 chat_id={chat_id}（{type(exc).__name__}）。"
                "确认小号已加入该群/频道，且 config.yaml 中的 chat_id 正确。"
            ) from exc
    return resolved
