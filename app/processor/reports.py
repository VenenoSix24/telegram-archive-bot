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


def format_help_report() -> str:
    """/start、/help 的命令一览（任务书 §44：命令要可发现，不全靠记忆）。"""
    return (
        "🤖 Telegram Archive Bot\n"
        "\n"
        "回复某条已归档消息使用：\n"
        "/tag <标签…> — 追加标签（空格分隔）\n"
        "/rating <0-5> — 设置评级，0 清除\n"
        "\n"
        "直接发送的管理命令：\n"
        "/status — 运行状态\n"
        "/queue — 队列概况\n"
        "/tags — Tag 统计\n"
        "/pause — 暂停队列\n"
        "/resume — 恢复队列\n"
        "/rethumb [N] — 补抓缩略图（默认 100 条）\n"
        "/id — 查看当前会话 id\n"
        "\n"
        "Web 后台可完成日常编辑，命令仅管理员可用。"
    )


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
