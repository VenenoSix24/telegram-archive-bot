"""事件处理：把收到的新消息接进归档管道（落库 → 入队）。

自动监听持续收到消息；指令消息（/tag 等，ADR 0002 观察）不归档，
已存在（去重）不入队。Album 经 record_message 的组级去重只入队一次。
"""

from __future__ import annotations

import logging
import sqlite3

from telethon import events

from app.config import Config
from app.media.backfill import backfill_thumbs
from app.media.thumbnails import ThumbnailCache
from app.processor.adapter import (
    IncomingMessage,
    build_incoming,
    resolve_source_url,
)
from app.processor.commands import parse_command
from app.processor.ratings import update_rating
from app.processor.recorder import add_manual_tags, record_message
from app.processor.reports import (
    format_queue_report,
    format_status_report,
    format_tag_report,
)
from app.queue.manager import QueueManager
from app.tags.engine import normalize_tags
from app.tags.index import compute_tag_counts

logger = logging.getLogger(__name__)


def _parse_rethumb_limit(args: list[str]) -> int:
    """`/rethumb [N]`：可选条数上限，缺省 100；非法值回退默认。"""
    if args:
        try:
            return max(1, int(args[0]))
        except ValueError:
            pass
    return 100


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


def attach_reply_command_handler(
    client, config: Config, conn: sqlite3.Connection, indexer=None
):
    """源群里对已归档消息回复 /tag 或 /rating 的补充处理。

    仅管理员（event.sender_id ∈ admins）生效；非指令回复忽略。
    indexer 非空时，/tag 应用后触发索引更新。
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
        if cmd not in ("tag", "rating"):
            return
        if cmd == "rating" and not config.rating_enabled:
            return
        row = conn.execute(
            "SELECT * FROM messages WHERE source_chat_id=? AND source_message_id=?",
            (event.chat_id, msg.reply_to_msg_id),
        ).fetchone()
        if row is None or not row["target_chat_id"]:
            return
        if cmd == "tag":
            manual = normalize_tags(" ".join(args))
            if not manual:
                return
            rendered = add_manual_tags(conn, row["id"], manual)
        else:
            if len(args) != 1:
                return
            try:
                value = int(args[0])
            except ValueError:
                return
            if not 0 <= value <= 5:
                return
            rendered = update_rating(conn, row["id"], value)
        if rendered is None:
            return
        await client.edit_message(
            row["target_chat_id"], row["target_message_id"], rendered
        )
        await client.delete_messages(event.chat_id, [msg.id])
        if cmd == "tag" and indexer is not None:
            indexer.schedule()
        logger.info(
            "reply %s on %s/%s applied to messages#%s",
            cmd,
            event.chat_id,
            msg.reply_to_msg_id,
            row["id"],
        )

    return on_reply_command


def attach_management_command_handler(
    client, config: Config, conn: sqlite3.Connection, queue: QueueManager
):
    """源群里管理员的管理命令：/status /queue /pause /resume /tags /id。

    回复类命令（/tag /rating）交给 attach_reply_command_handler；这里只处理
    非回复指令，且仅管理员（event.sender_id ∈ admins）。
    """
    ids = [c.chat_id for c in config.source_chats]
    if not ids:
        return None

    @client.on(events.NewMessage(chats=ids))
    async def on_management_command(event):
        msg = event.message
        if msg.reply_to_msg_id:
            return
        parsed = parse_command(msg.text)
        if parsed is None:
            return
        cmd, args = parsed
        if event.sender_id not in config.admins:
            return
        if cmd == "status":
            text = format_status_report(config, queue)
        elif cmd == "queue":
            text = format_queue_report(queue.stats())
        elif cmd == "tags":
            text = format_tag_report(compute_tag_counts(conn))
        elif cmd == "id":
            text = f"chat_id: {event.chat_id}\nsender_id: {event.sender_id}"
        elif cmd == "pause":
            queue.pause()
            text = "队列已暂停"
        elif cmd == "resume":
            queue.resume()
            text = "队列已恢复"
        elif cmd == "rethumb":
            limit = _parse_rethumb_limit(args)
            count = await backfill_thumbs(
                client, config, conn, ThumbnailCache(), limit=limit
            )
            text = f"已补抓 {count} 条缩略图"
        else:
            return
        await client.send_message(event.chat_id, text)
        logger.info("admin %s ran /%s", event.sender_id, cmd)

    return on_management_command
