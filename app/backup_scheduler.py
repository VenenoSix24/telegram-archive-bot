"""定时自动备份：本地 SQLite 备份 + 可选上传到指定 Telegram 会话。

计时语义针对「非 24 小时挂机」的使用方式：运行期间每小时巡检一次，
到期即备份；启动时若距上次备份已超过间隔，立刻补跑一次。因此
「每天备份」的实际含义是「程序运行期间每天备份」，停机期间顺延到
下次启动时补上。

「上次备份时间」取自本地最新一个 {数据库名}.*.bak 文件的 mtime，
重启不会造成重复备份。备份产物落在数据库同目录、沿用既有命名，
自动出现在 Web 后台备份列表并可下载。保留策略只清理本地文件
（保留最新 N 份），已上传到 Telegram 的副本永不删除。
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.config import Config
from app.web.backup import backup_database, validate_database_backup

logger = logging.getLogger(__name__)

# 运行期间的巡检周期：每小时看一次是否到期
CHECK_INTERVAL_SECONDS = 3600.0


class AutoBackupScheduler:
    """周期巡检并执行数据库自动备份（可选上传），失败只记日志不中断管道。"""

    def __init__(
        self, client, config: Config, check_interval: float = CHECK_INTERVAL_SECONDS
    ) -> None:
        self._client = client
        self._config = config
        self._check_interval = check_interval
        self._task: asyncio.Task | None = None

    # ---- 本地备份文件 ----

    def _backup_paths(self) -> list[Path]:
        """数据库同目录的全部备份文件；文件名含 UTC 时间戳，字典序即时间序。"""
        database = Path(self._config.database_path)
        return sorted(database.parent.glob(f"{database.name}.*.bak"))

    def _last_backup_at(self) -> datetime | None:
        paths = self._backup_paths()
        if not paths:
            return None
        newest_mtime = max(path.stat().st_mtime for path in paths)
        return datetime.fromtimestamp(newest_mtime, UTC)

    def is_due(self, now: datetime | None = None) -> bool:
        """距上次备份是否已达间隔；本地没有任何备份视为到期（首次必跑）。"""
        last = self._last_backup_at()
        if last is None:
            return True
        now = now or datetime.now(UTC)
        return now - last >= timedelta(days=self._config.backup_interval_days)

    # ---- 备份动作 ----

    async def run_once(self) -> Path | None:
        """执行一次备份（+可选上传+保留清理）；返回备份路径，失败返回 None。"""
        try:
            path = backup_database(Path(self._config.database_path))
        except Exception:
            logger.exception("auto backup failed for %s", self._config.database_path)
            return None
        try:
            validate_database_backup(path)
        except Exception:
            # 产物不可用直接删掉，避免坏文件混进 Web 备份列表
            logger.exception("auto backup validation failed, removing %s", path.name)
            path.unlink(missing_ok=True)
            return None
        logger.info("自动备份完成：%s", path.name)
        await self._upload(path)
        self._prune_local()
        return path

    async def _upload(self, path: Path) -> None:
        """按配置上传备份到指定会话；失败只记日志，本地备份仍然有效。"""
        chat_id = self._config.backup_upload_chat_id
        if chat_id is None or self._client is None:
            return
        try:
            await self._client.send_file(chat_id, path, caption=f"自动备份 {path.name}")
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("auto backup upload to %s failed", chat_id)

    def _prune_local(self) -> None:
        """保留最新 N 份本地备份，超出的删除；只动本地文件，不碰 Telegram 副本。"""
        paths = self._backup_paths()
        stale = paths[: max(0, len(paths) - self._config.backup_retain)]
        for path in stale:
            try:
                path.unlink()
            except OSError:
                logger.exception("auto backup prune failed for %s", path.name)
            else:
                logger.info("自动备份清理过期文件：%s", path.name)

    # ---- 生命周期（与 IndexUpdater 相同的 start/stop 约定） ----

    async def _maybe_backup(self) -> None:
        try:
            if self.is_due():
                await self.run_once()
        except asyncio.CancelledError:
            raise
        except Exception:
            # 巡检环节任何异常都不允许拖垮后台任务，否则之后永远不再备份
            logger.exception("auto backup check failed")

    async def run(self) -> None:
        # 启动即补跑：距上次备份超过间隔（或从未备份）时先备一次
        await self._maybe_backup()
        while True:
            await asyncio.sleep(self._check_interval)
            await self._maybe_backup()

    def start(self) -> None:
        if self._task is None and self._config.backup_enabled:
            self._task = asyncio.create_task(self.run())

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
