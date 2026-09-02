"""回复指令事件：/tag /rating 按副本模型应用（源群回复作用于全部副本）。"""

from __future__ import annotations

import logging
import sqlite3

from telethon import events

from app.config import Config
from app.processor.commands import parse_command
from app.processor.edit import apply_message_edit
from app.tags.engine import normalize_tags

logger = logging.getLogger(__name__)


def attach_reply_command_handler(
    client, config: Config, conn: sqlite3.Connection, indexer=None
):
    """回复指令 /tag /rating 的应用规则。

    源群里回复源消息 → 源级编辑（统一编辑服务）：更新父表与该源消息的
    全部目标副本（指令作用于共享的源）；
    目标频道里回复目标消息 → 只更新被回复的那条副本（独立副本模型）。
    旧数据没有副本行时由服务回退父级路径。仅管理员生效，指令回复会被删除。
    """
    source_ids = [c.chat_id for c in config.source_chats]
    target_ids = sorted(config.all_target_channel_ids())

    def _authorize(msg, sender_id):
        if not msg.reply_to_msg_id:
            return None
        parsed = parse_command(msg.text)
        if parsed is None:
            return None
        cmd, args = parsed
        if cmd not in ("tag", "rating") or sender_id not in config.admins:
            return None
        if cmd == "rating" and not config.rating_enabled:
            return None
        return cmd, args

    def _manual_tags(args):
        tags = normalize_tags(" ".join(args))
        return tags or None

    def _rating_value(args):
        if len(args) != 1:
            return None
        try:
            value = int(args[0])
        except ValueError:
            return None
        return value if 0 <= value <= 5 else None

    async def _apply(message_id: int, target_id: int | None, cmd: str, args) -> bool:
        if cmd == "tag":
            tags = _manual_tags(args)
            if not tags:
                return False
            return await apply_message_edit(
                client, conn, message_id, target_id=target_id, add_tags=tags,
                indexer=indexer,
            )
        value = _rating_value(args)
        if value is None:
            return False
        return await apply_message_edit(
            client, conn, message_id, target_id=target_id, rating=value,
            indexer=indexer,
        )

    if source_ids:
        @client.on(events.NewMessage(chats=source_ids))
        async def on_reply_command(event):
            msg = event.message
            authorized = _authorize(msg, event.sender_id)
            if authorized is None:
                return
            cmd, args = authorized
            row = conn.execute(
                "SELECT * FROM messages WHERE source_chat_id=? AND source_message_id=?",
                (event.chat_id, msg.reply_to_msg_id),
            ).fetchone()
            if row is None:
                return
            # 源级编辑交给统一编辑服务（E3）：服务内部写父表并镜像到全部
            # 归档副本；单副本失败不中断其余副本，也不会覆盖指令消息。
            try:
                ok = await _apply(row["id"], None, cmd, args)
            except Exception:
                logger.exception(
                    "reply %s failed for messages#%s", cmd, row["id"]
                )
                ok = False
            if not ok:
                return
            await client.delete_messages(event.chat_id, [msg.id])
            logger.info(
                "reply %s on %s/%s applied to messages#%s (all archived copies)",
                cmd, event.chat_id, msg.reply_to_msg_id, row["id"],
            )

    if target_ids:
        @client.on(events.NewMessage(chats=target_ids))
        async def on_target_reply_command(event):
            msg = event.message
            authorized = _authorize(msg, event.sender_id)
            if authorized is None:
                return
            cmd, args = authorized
            copy = conn.execute(
                "SELECT id, message_id FROM message_targets "
                "WHERE target_chat_id=? AND target_message_id=? AND status='archived'",
                (event.chat_id, msg.reply_to_msg_id),
            ).fetchone()
            if copy is None:
                return
            try:
                ok = await _apply(copy["message_id"], copy["id"], cmd, args)
            except Exception:
                logger.exception(
                    "reply %s failed for target#%s", cmd, copy["id"]
                )
                ok = False
            if not ok:
                return
            await client.delete_messages(event.chat_id, [msg.id])
            logger.info(
                "reply %s on target %s/%s applied to target#%s",
                cmd, event.chat_id, msg.reply_to_msg_id, copy["id"],
            )

    return None
