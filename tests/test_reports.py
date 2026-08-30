"""管理命令报表文本。"""

from __future__ import annotations

from app.config import Config, SourceChat
from app.database.migrate import apply_migrations, open_db
from app.processor.reports import (
    format_queue_report,
    format_status_report,
    format_tag_report,
)
from app.queue.manager import QueueManager, QueueStats


async def _ok(mid):
    return None


def _config() -> Config:
    return Config(
        api_id=1,
        api_hash="x",
        bot_token=None,
        source_chats=[
            SourceChat(chat_id=-1001, name="游戏", default_tags=["游戏"]),
            SourceChat(chat_id=-1003, name="中转群", default_tags=["历史"]),
        ],
        target_channel_id=-1009,
        forward_interval=3,
        retry_count=3,
        show_link=True,
        preserve_original=True,
        rating_enabled=True,
        admins=frozenset({1}),
        url_template=None,
        database_path="x.sqlite",
        config_path="config.yaml",
        web_enabled=False,
        web_host="127.0.0.1",
        web_port=8000,
        web_token="",
    )


def _queue(tmp_path):
    conn = open_db(tmp_path / "s.sqlite")
    apply_migrations(conn)
    return conn, QueueManager(conn, sender=_ok, interval=3, max_retries=3)


def test_format_queue_report():
    text = format_queue_report(QueueStats(pending=2, failed=1, estimate_seconds=6))
    assert "等待发送：2" in text
    assert "失败：1" in text
    assert "预计剩余：6" in text


def test_format_tag_report_empty():
    assert format_tag_report([]) == "暂无 Tag"


def test_format_tag_report_lines():
    assert format_tag_report([("游戏", 2), ("软件", 1)]) == "#游戏 · 2\n#软件 · 1"


def test_format_status_report_worker_state(tmp_path):
    conn, queue = _queue(tmp_path)
    text = format_status_report(_config(), queue)
    assert "游戏" in text
    assert "中转群" in text
    assert "运行中" in text
    queue.pause()
    assert "已暂停" in format_status_report(_config(), queue)
