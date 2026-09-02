"""新消息事件处理：指令过滤、落库、入队。

自动监听持续收到消息；指令消息（/tag 等，ADR 0002 观察）不归档，
已存在（去重）不入队。Album 经 record_message 的组级去重只入队一次。
"""

from __future__ import annotations

import logging
import sqlite3

from telethon import events

from app.config import Config
from app.processor.adapter import IncomingMessage, build_incoming, resolve_source_url
from app.processor.commands import parse_command
from app.processor.recorder import record_message
from app.queue.manager import QueueManager

logger = logging.getLogger(__name__)


def process_incoming(
    config: Config,
    conn: sqlite3.Connection,
    queue: QueueManager,
    incoming: IncomingMessage,
) -> bool:
    """落库并入队的决策：指令/已存在跳过，返回是否入队。"""
    if parse_command(incoming.text) is not None:
        return False
    chat_cfg = next(
        (c for c in config.source_chats if c.chat_id == incoming.source_chat_id), None
    )
    source_tags = chat_cfg.default_tags if chat_cfg else []
    message_id = record_message(
        conn,
        incoming,
        source_tags=source_tags,
        preserve_original=config.preserve_original,
        template_layout=config.message_template,
    )
    if message_id is None:
        return False
    queue.enqueue(message_id)
    logger.info("收到新消息，已加入队列（素材 #%s）", message_id)
    return True


def attach_new_message_handler(
    client,
    config: Config,
    conn: sqlite3.Connection,
    queue: QueueManager,
    indexer=None,
):
    """注册所有源群的新消息监听。indexer 非空时在归档后触发索引更新。"""
    ids = [c.chat_id for c in config.source_chats]

    @client.on(events.NewMessage(chats=ids))
    async def on_new_message(event):
        source_url = await resolve_source_url(
            client, event.message, event.chat, show_link=config.show_link
        )
        incoming = build_incoming(event.message, event.chat_id, source_url)
        try:
            if process_incoming(config, conn, queue, incoming) and indexer is not None:
                indexer.schedule()
        except Exception:
            logger.exception(
                "failed to process incoming %s/%s", event.chat_id, event.message.id
            )

    return on_new_message
