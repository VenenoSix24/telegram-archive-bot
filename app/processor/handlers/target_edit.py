"""目标频道编辑事件：Telegram 侧手动编辑正文写回对应副本。"""

from __future__ import annotations

import logging
import sqlite3

from telethon import events
from telethon.extensions import html as telegram_html

from app.config import Config
from app.processor.edit import apply_message_edit, extract_edited_body

logger = logging.getLogger(__name__)


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
