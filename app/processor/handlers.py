"""事件处理：把收到的新消息接进归档管道（落库 → 入队）。

自动监听持续收到消息；指令消息（/tag 等，ADR 0002 观察）不归档，
已存在（去重）不入队。Album 经 record_message 的组级去重只入队一次。
"""

from __future__ import annotations

import logging
import sqlite3

from telethon import events
from telethon.extensions import html as telegram_html

from app.config import Config
from app.media.backfill import backfill_thumbs
from app.media.thumbnails import ThumbnailCache, thumbs_dir_for
from app.processor.adapter import (
    IncomingMessage,
    build_incoming,
    resolve_source_url,
)
from app.processor.commands import parse_command
from app.processor.edit import apply_message_edit, extract_edited_body
from app.processor.recorder import record_message
from app.processor.reports import (
    format_help_report,
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


def attach_reply_command_handler(
    client, config: Config, conn: sqlite3.Connection, indexer=None
):
    """回复指令 /tag /rating 的应用规则。

    源群里回复源消息 → 更新该源消息的全部目标副本（指令作用于共享的源）；
    目标频道里回复目标消息 → 只更新被回复的那条副本（独立副本模型）。
    旧数据没有副本行时回退父级路径。仅管理员生效，指令回复会被删除。
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
            copies = conn.execute(
                "SELECT id FROM message_targets WHERE message_id=? AND status='archived'",
                (row["id"],),
            ).fetchall()
            if copies:
                ok = True
                for copy in copies:
                    try:
                        applied = await _apply(row["id"], copy["id"], cmd, args)
                    except Exception:
                        logger.exception(
                            "reply %s failed for messages#%s target#%s",
                            cmd, row["id"], copy["id"],
                        )
                        applied = False
                    ok = applied and ok
            elif row["target_chat_id"]:
                ok = await _apply(row["id"], None, cmd, args)
            else:
                return
            if not ok:
                return
            await client.delete_messages(event.chat_id, [msg.id])
            logger.info(
                "reply %s on %s/%s applied to messages#%s (%s copies)",
                cmd, event.chat_id, msg.reply_to_msg_id, row["id"], len(copies),
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


def attach_target_edit_handler(client, config: Config, conn: sqlite3.Connection, indexer=None):
    """将 Telegram 目标消息的手动正文编辑写回对应副本。

    只更新被编辑的那条副本（独立副本模型）：不做兄弟副本传播，
    也不需要开关——用户在 Telegram 改了哪条，Web 就同步哪条。
    """
    ids = list(config.all_target_channel_ids())
    if not ids:
        return None

    @client.on(events.MessageEdited(chats=ids))
    async def on_target_edited(event):
        row = conn.execute(
            "SELECT mt.id AS target_id, mt.message_id, m.source_url "
            "FROM message_targets mt JOIN messages m ON m.id=mt.message_id "
            "WHERE mt.target_chat_id=? AND mt.target_message_id=? AND mt.status='archived'",
            (event.chat_id, event.message.id),
        ).fetchone()
        if row is None:
            return
        tags = [
            tag["name"]
            for tag in conn.execute(
                "SELECT t.name FROM target_tags tt JOIN tags t ON t.id=tt.tag_id "
                "WHERE tt.target_id=? ORDER BY tt.rowid",
                (row["target_id"],),
            )
        ]
        text = event.message.message or ""
        html_text = telegram_html.unparse(
            text, getattr(event.message, "entities", None) or []
        )
        # 用户编辑的是完整渲染结果，先剥离评级/Tag/来源骨架再回写正文，
        # 否则重渲染会把模板再套一层（套娃 bug）。
        body, body_html = extract_edited_body(
            text,
            html_text,
            tags=tags,
            source_url=row["source_url"],
        )
        await apply_message_edit(
            client,
            conn,
            row["message_id"],
            target_id=row["target_id"],
            body=body,
            body_html=body_html or None,
            indexer=indexer,
        )

    return on_target_edited


def attach_target_delete_handler(client, config: Config, conn: sqlite3.Connection):
    """监听目标频道删除事件，只标记目标副本，不删除数据库记录。"""
    ids = list(config.all_target_channel_ids())
    if not ids:
        return None

    @client.on(events.MessageDeleted(chats=ids))
    async def on_target_deleted(event):
        for telegram_message_id in event.deleted_ids:
            conn.execute(
                "UPDATE message_targets SET status='deleted' "
                "WHERE target_chat_id=? AND target_message_id=?",
                (event.chat_id, telegram_message_id),
            )
        conn.commit()

    return on_target_deleted


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
