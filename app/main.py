"""V1 entry point：连接、校验 chat、启动归档管道（监听 → 队列 → 复制）。"""

from __future__ import annotations

import asyncio
import logging
from contextlib import suppress

from app.config import ConfigError, load_config
from app.database.migrate import apply_migrations, open_db
from app.logging_setup import setup_logging
from app.processor.handlers import (
    attach_management_command_handler,
    attach_new_message_handler,
    attach_reply_command_handler,
    attach_target_delete_handler,
    attach_target_edit_handler,
)
from app.queue.manager import QueueManager
from app.tags.indexer import IndexUpdater
from app.telegram.client import build_client, resolve_chat_names, validate_config_chats
from app.telegram.copier import archive_message_by_db_id
from app.web.server import start_server_task

logger = logging.getLogger(__name__)


async def _serve_web(web_server) -> None:
    """Keep uvicorn startup failures from taking down the Telegram worker."""
    try:
        await web_server.serve()
    except SystemExit as exc:
        logger.error("web server stopped during startup (exit code %s)", exc.code)


async def _run() -> int:
    setup_logging()
    try:
        config = load_config()
    except ConfigError as exc:
        logger.error("%s", exc)
        return 2

    logger.info("database: %s", config.database_path)
    conn = open_db(config.database_path)
    apply_migrations(conn)

    client = build_client(config)
    await client.connect()
    if not await client.is_user_authorized():
        logger.warning("尚未登录：请先运行 python -m app.auth")
        await client.disconnect()
        conn.close()
        return 3

    chats = await resolve_chat_names(client, config)
    try:
        validate_config_chats_result = await validate_config_chats(client, config)
        chats.update(validate_config_chats_result)
    except RuntimeError as exc:
        logger.error("%s", exc)
        await client.disconnect()
        conn.close()
        return 4

    for src in config.source_chats:
        target_ids = config.targets_for(src.chat_id)
        logger.info(
            "source: %s (%s) -> targets %s",
            chats[src.chat_id],
            src.chat_id,
            ", ".join(
                f"{chats.get(target_id, target_id)} ({target_id})"
                for target_id in target_ids
            ),
        )

    for target_id in sorted(config.all_target_channel_ids()):
        target = await client.get_entity(target_id)
        is_admin = bool(
            getattr(target, "creator", False) or getattr(target, "admin_rights", None)
        )
        if not is_admin:
            logger.warning(
                "目标频道 %s (%s)：当前账号不是管理员，将无法发消息/编辑。"
                "请把小号设为该频道管理员。",
                chats[target_id],
                target_id,
            )

    queue = QueueManager(
        conn,
        sender=lambda mid: archive_message_by_db_id(client, config, conn, mid),
        interval=config.forward_interval,
        max_retries=config.retry_count,
    )
    recovered = queue.recover_incomplete()
    if recovered:
        logger.info("重启恢复 %s 条 processing 任务为 pending", recovered)
    worker = asyncio.create_task(queue.run())
    indexer = IndexUpdater(client, config, conn)
    indexer.start()
    attach_new_message_handler(client, config, conn, queue, indexer)
    attach_reply_command_handler(client, config, conn, indexer)
    attach_target_edit_handler(client, config, conn, indexer)
    attach_target_delete_handler(client, config, conn)
    attach_management_command_handler(client, config, conn, queue)

    web_server = None
    if config.web_enabled:
        web_server = start_server_task(
            config, client=client, conn=conn, indexer=indexer, chat_names=chats
        )
        web_task = asyncio.create_task(_serve_web(web_server))

    logger.info("connected，归档管道运行中——Ctrl+C 停止")
    try:
        await client.run_until_disconnected()
    finally:
        if web_server is not None:
            web_server.should_exit = True
            with suppress(asyncio.CancelledError):
                await web_task
        worker.cancel()
        with suppress(asyncio.CancelledError):
            await worker
        await indexer.stop()
        await client.disconnect()
        conn.close()
    return 0


def main() -> None:
    raise SystemExit(asyncio.run(_run()))


if __name__ == "__main__":
    main()
