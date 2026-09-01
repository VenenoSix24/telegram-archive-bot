"""Structured logging: stdout + rotating app.log and error.log.

日志文件按大小轮转，保留 5 份；error.log 只记 WARNING 及以上。
log_dir 由调用方按配置目录解析（app.config.config_dir），不依赖 CWD。
"""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

_FORMAT = "%(asctime)s %(levelname)s [%(name)s] %(message)s"


def setup_logging(log_dir: Path) -> None:
    root = logging.getLogger()
    if getattr(root, "_archive_configured", False):
        return
    log_dir.mkdir(parents=True, exist_ok=True)
    root.setLevel(logging.INFO)
    formatter = logging.Formatter(_FORMAT)

    console = logging.StreamHandler()
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
    root._archive_configured = True
