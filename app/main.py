"""V1 entry point：连接 Telegram、校验配置的 chat 可访问性、保持运行。

Phase 2 起在此注册事件处理器；队列 worker 也在进程内协程运行。
"""

from __future__ import annotations

import asyncio
import logging

from app.config import ConfigError, load_config
from app.logging_setup import setup_logging
from app.telegram.client import build_client, validate_config_chats

logger = logging.getLogger(__name__)


async def _run() -> int:
    setup_logging()
    try:
        config = load_config()
    except ConfigError as exc:
        logger.error("%s", exc)
        return 2

    client = build_client(config)
    await client.connect()
    if not await client.is_user_authorized():
        logger.warning("尚未登录：请先运行 python -m app.auth")
        await client.disconnect()
        return 3

    try:
        chats = await validate_config_chats(client, config)
    except RuntimeError as exc:
        logger.error("%s", exc)
        await client.disconnect()
        return 4

    for src in config.source_chats:
        logger.info("source: %s (%s)", chats[src.chat_id], src.chat_id)
    logger.info("target: %s (%s)", chats[config.target_channel_id], config.target_channel_id)
    if config.relay_chat_id:
        logger.info("relay: %s (%s)", chats[config.relay_chat_id], config.relay_chat_id)

    if not await client.is_admin(config.target_channel_id):
        logger.warning(
            "目标频道：当前账号不是管理员，将无法发消息/编辑。请把专用小号设为频道管理员。"
        )

    logger.info("connected，监听与归档功能在后续 Phase 接入——Ctrl+C 停止")
    try:
        await client.run_until_disconnected()
    finally:
        await client.disconnect()
    return 0


def main() -> None:
    raise SystemExit(asyncio.run(_run()))


if __name__ == "__main__":
    main()
