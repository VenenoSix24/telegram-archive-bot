"""总频道 Tag 索引：置顶消息的创建与防抖自动更新（Phase 9 事件层）。

索引文本为「📚 Tags」+ 每行 #tag · count（文档第 22 节）；Tag 数据变化时
schedule() 触发，经防抖窗口合并成一次 edit，避免高频变化打爆 Telegram。
多对多场景下每个目标频道各维护一条置顶索引消息（settings 按频道存 id）。
"""

from __future__ import annotations

import asyncio
import logging
import sqlite3

from telethon.errors import MessageNotModifiedError

from app.tags.index import compute_tag_counts, format_tag_index

logger = logging.getLogger(__name__)

SETTING_PREFIX = "tag_index_message_id:"
DEBOUNCE_SECONDS = 3.0


class IndexUpdater:
    def __init__(
        self, client, config, conn: sqlite3.Connection, debounce: float = DEBOUNCE_SECONDS
    ) -> None:
        self._client = client
        self._config = config
        self._conn = conn
        self._debounce = debounce
        self._dirty = asyncio.Event()
        self._task: asyncio.Task | None = None

    def _setting_key(self, target_chat_id: int) -> str:
        return f"{SETTING_PREFIX}{target_chat_id}"

    def schedule(self) -> None:
        """标记索引需要更新（防抖窗口内多次调用合并为一次）。"""
        self._dirty.set()

    async def _index_message_id(self, target_chat_id: int) -> int | None:
        row = self._conn.execute(
            "SELECT value FROM settings WHERE key=?", (self._setting_key(target_chat_id),)
        ).fetchone()
        return int(row["value"]) if row else None

    async def ensure_initial(self) -> None:
        """为尚未建设索引的目标频道创建置顶消息（幂等）。

        单个频道失败（如账号无发言/置顶权限）只记日志跳过，不拖垮其他
        频道，也不让整个索引任务死亡；失败频道保留无索引状态，
        _refresh_one 会跳过它。
        """
        for target_id in sorted(self._config.all_target_channel_ids()):
            if await self._index_message_id(target_id):
                continue
            try:
                target = await self._client.get_entity(target_id)
                msg = await self._client.send_message(target, format_tag_index([]))
                await self._client.pin_message(target, msg.id)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("tag index init failed for %s, skipped", target_id)
                continue
            self._conn.execute(
                "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                (self._setting_key(target_id), str(msg.id)),
            )
            self._conn.commit()
            logger.info("已为频道 %s 创建 Tag 索引置顶消息 #%s", target_id, msg.id)

    async def _refresh_one(self, target_chat_id: int) -> None:
        index_id = await self._index_message_id(target_chat_id)
        if index_id is None:
            return
        counts = compute_tag_counts(self._conn, target_chat_id=target_chat_id)
        target = await self._client.get_entity(target_chat_id)
        try:
            await self._client.edit_message(target, index_id, format_tag_index(counts))
        except MessageNotModifiedError:
            # 内容与目标一致时 Telegram 报 not modified，属正常空转，无需重试
            logger.debug("tag index unchanged in %s, skip edit", target_chat_id)

    async def _refresh_all(self) -> None:
        for target_id in sorted(self._config.all_target_channel_ids()):
            try:
                await self._refresh_one(target_id)
            except Exception:
                logger.exception("tag index refresh failed for %s", target_id)

    async def run(self) -> None:
        # 初始化失败不能让整个索引任务静默死亡——那之后 Tag 变化永远
        # 不会反映到 Telegram 侧；记录后继续进入防抖循环。
        try:
            await self.ensure_initial()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("tag index init failed, continuing without initial pin")
        while True:
            await self._dirty.wait()
            self._dirty.clear()
            await asyncio.sleep(self._debounce)
            await self._refresh_all()

    def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self.run())

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
