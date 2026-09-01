"""限速出站队列。

调度逻辑独立于具体发送：worker 按入队顺序消费 pending 任务，
每次发送后等待 interval 秒；失败达上限标记 failed 跳过不阻塞后续
（ADR 0001/b）；FloodWait 用异常对象上的 seconds 属性识别（Telethon
的 FloodWaitError 即带该属性），命中则整队暂停至等待结束；/pause
可人为暂停，/resume 恢复；重启时残留的 processing 回退为 pending。
"""

from __future__ import annotations

import asyncio
import logging
import sqlite3
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

logger = logging.getLogger(__name__)

STATUS_PENDING = "pending"
STATUS_PROCESSING = "processing"
STATUS_SUCCESS = "success"
STATUS_FAILED = "failed"

# 发送函数：把 message_id 对应的源消息归档到目标频道（回填 DB 由发送方负责）。
Sender = Callable[[int], Awaitable[None]]


@dataclass
class QueueStats:
    pending: int
    failed: int
    estimate_seconds: int


def is_flood_wait(exc: BaseException) -> int:
    """返回 FloodWait 秒数；非 FloodWait 返回 0。"""
    seconds = getattr(exc, "seconds", None)
    if isinstance(seconds, (int, float)) and seconds > 0:
        return int(seconds)
    return 0


class QueueManager:
    def __init__(
        self,
        conn: sqlite3.Connection,
        sender: Sender,
        interval: float,
        max_retries: int,
    ) -> None:
        self._conn = conn
        self._sender = sender
        self._interval = interval
        self._max_retries = max_retries
        self._paused = asyncio.Event()
        self._paused.set()

    def enqueue(self, message_id: int) -> None:
        self._conn.execute(
            "INSERT INTO queue (message_id, status, retry_count) VALUES (?, ?, 0)",
            (message_id, STATUS_PENDING),
        )
        self._conn.commit()

    def recover_incomplete(self) -> int:
        """重启后将残留 processing 回退为 pending，避免任务卡死（文档第 45 节）。"""
        cur = self._conn.execute(
            f"UPDATE queue SET status='{STATUS_PENDING}' WHERE status='{STATUS_PROCESSING}'"
        )
        self._conn.commit()
        return cur.rowcount

    def pause(self) -> None:
        self._paused.clear()

    def resume(self) -> None:
        self._paused.set()

    def is_paused(self) -> bool:
        return not self._paused.is_set()

    def stats(self) -> QueueStats:
        row = self._conn.execute(
            "SELECT "
            "SUM(status='pending') AS pending, "
            "SUM(status='failed') AS failed "
            "FROM queue"
        ).fetchone()
        pending = row["pending"] or 0
        failed = row["failed"] or 0
        return QueueStats(
            pending=pending,
            failed=failed,
            estimate_seconds=int(pending * self._interval),
        )

    def _next_pending(self):
        return self._conn.execute(
            "SELECT id, message_id FROM queue WHERE status=? ORDER BY id LIMIT 1",
            (STATUS_PENDING,),
        ).fetchone()

    async def _process_one(self, queue_id: int, message_id: int) -> int:
        """发送一条并更新状态；返回 FloodWait 秒数（0 表示正常完成或普通失败）。"""
        self._conn.execute(
            f"UPDATE queue SET status='{STATUS_PROCESSING}' WHERE id=?", (queue_id,)
        )
        self._conn.commit()
        try:
            await self._sender(message_id)
        except asyncio.CancelledError:
            # 关机取消：任务回退 pending 供下次启动重发，取消本身继续向上传播，
            # 吞掉它会导致 worker 永远无法退出（进程关不掉）
            self._conn.execute(
                "UPDATE queue SET status=?, last_error='cancelled' WHERE id=?",
                (STATUS_PENDING, queue_id),
            )
            self._conn.commit()
            raise
        except Exception as exc:
            if flood := is_flood_wait(exc):
                self._conn.execute(
                    "UPDATE queue SET status=?, last_error=? WHERE id=?",
                    (STATUS_PENDING, f"flood_wait {flood}s", queue_id),
                )
                self._conn.commit()
                return flood
            row = self._conn.execute(
                "SELECT retry_count FROM queue WHERE id=?", (queue_id,)
            ).fetchone()
            retries = row["retry_count"] if row else 0
            retries += 1
            status = STATUS_FAILED if retries >= self._max_retries else STATUS_PENDING
            self._conn.execute(
                "UPDATE queue SET retry_count=?, status=?, last_error=? WHERE id=?",
                (retries, status, repr(exc), queue_id),
            )
            self._conn.commit()
            logger.warning(
                "queue %s failed (retry %s/%s): %r",
                queue_id,
                retries,
                self._max_retries,
                exc,
            )
            return 0
        self._conn.execute(f"UPDATE queue SET status='{STATUS_SUCCESS}' WHERE id=?", (queue_id,))
        self._conn.commit()
        return 0

    async def run(self) -> None:
        while True:
            await self._paused.wait()
            row = self._next_pending()
            if row is None:
                await asyncio.sleep(self._interval)
                continue
            flood = await self._process_one(row["id"], row["message_id"])
            if flood:
                logger.warning("FloodWait %ss，队列暂停 %s 秒", flood, flood)
                await asyncio.sleep(flood)
            else:
                await asyncio.sleep(self._interval)
