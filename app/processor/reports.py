"""管理命令的报表文本生成（纯函数，可测）。"""

from __future__ import annotations

from app.config import Config
from app.queue.manager import QueueManager, QueueStats


def format_queue_report(stats: QueueStats) -> str:
    return (
        f"等待发送：{stats.pending}\n"
        f"失败：{stats.failed}\n"
        f"预计剩余：{stats.estimate_seconds} 秒"
    )


def format_tag_report(counts: list[tuple[str, int]]) -> str:
    if not counts:
        return "暂无 Tag"
    return "\n".join(f"#{name} · {count}" for name, count in counts)


def format_status_report(config: Config, queue: QueueManager) -> str:
    targets = "、".join(str(t) for t in sorted(config.all_target_channel_ids()))
    stats = queue.stats()
    worker = "已暂停" if queue.is_paused() else "运行中"
    return (
        "Telegram：正常\n"
        f"监听：{'、'.join(c.name or str(c.chat_id) for c in config.source_chats)}\n"
        f"目标频道：{targets}\n"
        f"队列：等待 {stats.pending}，失败 {stats.failed}\n"
        "Database：正常\n"
        f"Worker：{worker}"
    )
