"""目标频道删除事件：只标记目标副本墓碑，不删除数据库记录。"""

from __future__ import annotations

import logging
import sqlite3

from telethon import events

from app.config import Config

logger = logging.getLogger(__name__)


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
