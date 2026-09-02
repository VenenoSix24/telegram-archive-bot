"""事件处理包：五个事件 handler 各自独立成模块（E2）。

- incoming：新消息 → 落库入队（attach_new_message_handler / process_incoming）
- reply_commands：源群/目标频道回复指令 /tag /rating
- target_edit：目标频道消息编辑写回副本
- target_delete：目标频道消息删除标记墓碑
- management：源群管理员命令 /status /queue /pause /resume /tags /id /rethumb

公开 API 与拆分前的 app.processor.handlers 模块完全一致。
"""

from __future__ import annotations

from app.processor.handlers.incoming import attach_new_message_handler, process_incoming
from app.processor.handlers.management import (
    _parse_rethumb_limit,
    attach_management_command_handler,
)
from app.processor.handlers.reply_commands import attach_reply_command_handler
from app.processor.handlers.target_delete import attach_target_delete_handler
from app.processor.handlers.target_edit import attach_target_edit_handler

__all__ = [
    "_parse_rethumb_limit",
    "attach_management_command_handler",
    "attach_new_message_handler",
    "attach_reply_command_handler",
    "attach_target_delete_handler",
    "attach_target_edit_handler",
    "process_incoming",
]
