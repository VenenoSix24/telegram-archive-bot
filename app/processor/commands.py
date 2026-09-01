"""管理命令解析。

Phase 6/7 的命令（/tag /rating）与管理命令（/status /queue …）共用入口；
权限校验与回复编排在 Telegram 事件层（Phase 10 统一管理）。
"""

from __future__ import annotations

MANAGEMENT_COMMANDS = {"tag", "rating", "status", "queue", "pause", "resume", "tags", "id"}


def parse_command(text: str | None) -> tuple[str, list[str]] | None:
    """解析 '/rating 5' → ('rating', ['5'])；非管理命令返回 None。

    兼容 '@botname' 后缀（/rating@bot 5）与大小写差异。
    """
    if not text or not text.startswith("/"):
        return None
    parts = text.split()
    name = parts[0][1:].split("@")[0].lower()
    if name not in MANAGEMENT_COMMANDS:
        return None
    return name, parts[1:]
