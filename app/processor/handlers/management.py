"""源群管理命令事件：/status /queue /pause /resume /tags /id /rethumb。"""

from __future__ import annotations

import logging
import sqlite3

from telethon import events

from app.config import Config
from app.media.backfill import backfill_thumbs
from app.media.thumbnails import ThumbnailCache, thumbs_dir_for
from app.processor.commands import parse_command
from app.processor.reports import (
    format_help_report,
    format_queue_report,
    format_status_report,
    format_tag_report,
)
from app.queue.manager import QueueManager
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
        if cmd in ("start", "help"):
            text = format_help_report()
        elif cmd == "status":
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
                client,
                config,
                conn,
                ThumbnailCache(thumbs_dir_for(config.database_path)),
                limit=limit,
            )
            text = f"已补抓 {count} 条缩略图"
        else:
            return
        await client.send_message(event.chat_id, text)
        logger.info("admin %s ran /%s", event.sender_id, cmd)

    return on_management_command
