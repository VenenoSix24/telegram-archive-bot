"""Structured logging: stdout + rotating app.log and error.log.

文件双份按大小轮转：app.log 全量（INFO+）、error.log 只记 WARNING+。
终端面向人：默认只放行 app 自身的日志，telethon/asyncio 等第三方库的
技术噪音降到 WARNING 才显示；需要排查时用 LOG_LEVEL=DEBUG 或看 app.log。
"""

from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

_FORMAT = "%(asctime)s %(levelname)s [%(name)s] %(message)s"

# 这些库的 INFO（收发包、连接状态）对使用者是噪音，文件里也只留 WARNING+
_NOISY_LOGGERS = ("telethon", "asyncio", "urllib3")


class _AppOnlyFilter(logging.Filter):
    """终端只显示 app.* 的日志与所有 WARNING+ 记录。"""

    def filter(self, record: logging.LogRecord) -> bool:
        return record.name.startswith("app.") or record.levelno >= logging.WARNING


def setup_logging(log_dir: Path) -> None:
    root = logging.getLogger()
    if getattr(root, "_archive_configured", False):
        return
    log_dir.mkdir(parents=True, exist_ok=True)
    root.setLevel(logging.INFO)
    formatter = logging.Formatter(_FORMAT)

    console = logging.StreamHandler()
    level_name = os.getenv("LOG_LEVEL", "INFO").strip().upper()
    console.setLevel(getattr(logging, level_name, logging.INFO))
    console.addFilter(_AppOnlyFilter())
    console.setFormatter(formatter)

    app_file = RotatingFileHandler(
        log_dir / "app.log", maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )
    app_file.setFormatter(formatter)

    error_file = RotatingFileHandler(
        log_dir / "error.log", maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )
    error_file.setLevel(logging.WARNING)
    error_file.setFormatter(formatter)

    root.addHandler(console)
    root.addHandler(app_file)
    root.addHandler(error_file)
    for name in _NOISY_LOGGERS:
        logging.getLogger(name).setLevel(logging.WARNING)
    root._archive_configured = True
