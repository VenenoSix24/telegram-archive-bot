"""事件处理：把收到的新消息接进归档管道（落库 → 入队）。

自动监听持续收到消息；指令消息（/tag 等，ADR 0002 观察）不归档，
已存在（去重）不入队。Album 经 record_message 的组级去重只入队一次。
"""

from __future__ import annotations

import logging
import sqlite3

from telethon import events

from app.config import Config
from app.processor.adapter import (
    IncomingMessage,
    build_incoming,
    resolve_source_url,
)
from app.processor.commands import parse_command
from app.processor.recorder import add_manual_tags, record_message
from app.queue.manager import QueueManager
from app.tags.engine import normalize_tags

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
    )
    if message_id is None:
        return False
    queue.enqueue(message_id)
    logger.info("enqueued messages#%s from %s", message_id, incoming.source_chat_id)
    return True


def attach_new_message_handler(
    client, config: Config, conn: sqlite3.Connection, queue: QueueManager
):
    """注册所有源群的新消息监听。"""
    ids = [c.chat_id for c in config.source_chats]

    @client.on(events.NewMessage(chats=ids))
    async def on_new_message(event):
        source_url = await resolve_source_url(
            client, event.message, event.chat, show_link=config.show_link
        )
        incoming = build_incoming(event.message, event.chat_id, source_url)
        try:
            process_incoming(config, conn, queue, incoming)
        except Exception:
            logger.exception(
                "failed to process incoming %s/%s", event.chat_id, event.message.id
            )

    return on_new_message


def attach_reply_command_handler(client, config: Config, conn: sqlite3.Connection):
    """源群里对已归档消息回复 /tag 的补充处理：追加 tag→重渲染→编辑→删指令。

    仅管理员（event.sender_id ∈ admins）生效；非指令回复忽略。
    """
    ids = [c.chat_id for c in config.source_chats]
    if not ids:
        return None

    @client.on(events.NewMessage(chats=ids))
    async def on_reply_command(event):
        msg = event.message
        if not msg.reply_to_msg_id:
            return
        parsed = parse_command(msg.text)
        if parsed is None:
            return
        cmd, args = parsed
        if event.sender_id not in config.admins:
            return
        if cmd != "tag":
            return
        manual = normalize_tags(" ".join(args))
        if not manual:
            return
        row = conn.execute(
            "SELECT * FROM messages WHERE source_chat_id=? AND source_message_id=?",
            (event.chat_id, msg.reply_to_msg_id),
        ).fetchone()
        if row is None or not row["target_chat_id"]:
            return
        rendered = add_manual_tags(conn, row["id"], manual)
        if rendered is None:
            return
        await client.edit_message(
            row["target_chat_id"], row["target_message_id"], rendered
        )
        await client.delete_messages(event.chat_id, [msg.id])
        logger.info(
            "reply /tag on %s/%s applied to messages#%s",
            event.chat_id,
            msg.reply_to_msg_id,
            row["id"],
        )

    return on_reply_command
