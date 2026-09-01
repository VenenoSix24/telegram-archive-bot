"""Queue 调度：状态流转、失败跳过、FloodWait、重启恢复、顺序。

queue.message_id 外键到 messages.id，入队前需先有对应 messages 记录
（Phase 3 流程：收到消息→写 messages→enqueue(messages.id)）。
"""

from __future__ import annotations

import asyncio
from contextlib import suppress

from app.database.migrate import apply_migrations, open_db
from app.queue.manager import QueueManager


class FakeFlood(Exception):
    def __init__(self, seconds: int) -> None:
        self.seconds = seconds
        super().__init__(f"FakeFlood {seconds}s")


async def _ok(mid):
    return None


def _setup(tmp_path, sender, interval=0.1, max_retries=3):
    conn = open_db(tmp_path / "q.sqlite")
    apply_migrations(conn)
    return conn, QueueManager(conn, sender, interval=interval, max_retries=max_retries)


def _seed_message(conn, mid: int) -> None:
    conn.execute(
        "INSERT INTO messages (id, source_chat_id, source_message_id) VALUES (?, -1001, ?)",
        (mid, mid),
    )
    conn.commit()


def _row(conn, column, index=0):
    rows = conn.execute(f"SELECT {column} FROM queue ORDER BY id").fetchall()
    return rows[index][column]


def test_enqueue_sets_pending(tmp_path):
    conn, q = _setup(tmp_path, sender=_ok)
    _seed_message(conn, 1)
    q.enqueue(1)
    assert _row(conn, "status") == "pending"
    assert _row(conn, "message_id") == 1


def test_recover_processing_to_pending(tmp_path):
    conn, q = _setup(tmp_path, sender=_ok)
    _seed_message(conn, 1)
    q.enqueue(1)
    conn.execute("UPDATE queue SET status='processing'")
    conn.commit()
    assert q.recover_incomplete() == 1
    assert _row(conn, "status") == "pending"


async def test_success_marks_success(tmp_path):
    conn, q = _setup(tmp_path, sender=_ok)
    _seed_message(conn, 1)
    q.enqueue(1)
    await q._process_one(_row(conn, "id"), 1)
    assert _row(conn, "status") == "success"


async def test_retry_pending_until_limit_then_failed(tmp_path):
    seen = []

    async def flaky(mid):
        seen.append(mid)
        raise RuntimeError("net down")

    conn, q = _setup(tmp_path, sender=flaky, max_retries=2)
    _seed_message(conn, 1)
    q.enqueue(1)
    qid = _row(conn, "id")

    await q._process_one(qid, 1)
    assert _row(conn, "retry_count") == 1
    assert _row(conn, "status") == "pending"

    await q._process_one(qid, 1)
    assert _row(conn, "retry_count") == 2
    assert _row(conn, "status") == "failed"
    assert seen == [1, 1]


async def test_failure_does_not_block_next(tmp_path):
    async def sender(mid):
        if mid == 101:
            raise RuntimeError("bad")

    conn, q = _setup(tmp_path, sender=sender, max_retries=2)
    _seed_message(conn, 101)
    _seed_message(conn, 102)
    q.enqueue(101)
    q.enqueue(102)
    ids = [r["id"] for r in conn.execute("SELECT id FROM queue ORDER BY id")]
    first, second = ids[0], ids[1]
    await q._process_one(first, 101)
    await q._process_one(first, 101)
    await q._process_one(second, 102)
    statuses = [r["status"] for r in conn.execute("SELECT status FROM queue ORDER BY id")]
    assert statuses == ["failed", "success"]


async def test_flood_wait_keeps_pending(tmp_path):
    async def flood(_mid):
        raise FakeFlood(9)

    conn, q = _setup(tmp_path, sender=flood, max_retries=3)
    _seed_message(conn, 1)
    q.enqueue(1)
    qid = _row(conn, "id")
    wait = await q._process_one(qid, 1)
    assert wait == 9
    assert _row(conn, "status") == "pending"
    assert "flood_wait" in _row(conn, "last_error")


async def test_cancel_restores_pending_and_reraises(tmp_path):
    """关机取消：任务回退 pending 且取消继续传播，worker 才能退出。"""
    async def slow(mid):
        await asyncio.sleep(10)

    conn, q = _setup(tmp_path, sender=slow, max_retries=3)
    _seed_message(conn, 1)
    q.enqueue(1)
    qid = _row(conn, "id")

    task = asyncio.create_task(q._process_one(qid, 1))
    await asyncio.sleep(0.05)
    task.cancel()
    with suppress(asyncio.CancelledError):
        await task

    assert _row(conn, "status") == "pending"
    assert "cancelled" in _row(conn, "last_error")


def test_stats(tmp_path):
    conn, q = _setup(tmp_path, sender=_ok, interval=3)
    _seed_message(conn, 1)
    _seed_message(conn, 2)
    q.enqueue(1)
    q.enqueue(2)
    conn.execute("UPDATE queue SET status='failed' WHERE id=(SELECT id FROM queue LIMIT 1)")
    conn.commit()
    stats = q.stats()
    assert stats.pending == 1
    assert stats.failed == 1
    assert stats.estimate_seconds == 3


def test_pause_resume(tmp_path):
    conn, q = _setup(tmp_path, sender=_ok)
    assert q._paused.is_set()
    q.pause()
    assert not q._paused.is_set()
    q.resume()
    assert q._paused.is_set()


async def test_run_drains_in_order(tmp_path):
    conn = open_db(tmp_path / "q.sqlite")
    apply_migrations(conn)
    drained = asyncio.Event()
    done = []

    async def sender(mid):
        done.append(mid)
        if len(done) == 3:
            drained.set()

    q = QueueManager(conn, sender, interval=0.01, max_retries=3)
    for mid in (101, 102, 103):
        _seed_message(conn, mid)
        q.enqueue(mid)

    task = asyncio.create_task(q.run())
    try:
        await asyncio.wait_for(drained.wait(), timeout=3)
    finally:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task

    assert done == [101, 102, 103]
    assert q.stats().pending == 0
