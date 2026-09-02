"""运维端点：备份列举/下载/删除、恢复/导入/创建、重置数据库。"""

from __future__ import annotations

import logging
import shutil
import sqlite3
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse

from app.web.backup import (
    backup_config,
    backup_database,
    backup_metadata,
    import_backup,
    reset_database,
    validate_database_backup,
)
from app.web.routes.deps import WebContext

logger = logging.getLogger(__name__)


def build_router(ctx: WebContext) -> APIRouter:
    router = APIRouter()

    def _backup_paths() -> list[tuple[Path, str]]:
        database = Path(ctx.database_path)
        configuration = Path(ctx.config_path)
        return [
            *((path, "database") for path in database.parent.glob(f"{database.name}.*.bak")),
            *((path, "config") for path in configuration.parent.glob(
                f"{configuration.name}.*.bak"
            )),
        ]

    def _find_backup(name: str) -> tuple[Path, str]:
        if not isinstance(name, str) or Path(name).name != name or not name.endswith(".bak"):
            raise HTTPException(status_code=400, detail="invalid backup name")
        for path, kind in _backup_paths():
            if path.name == name:
                return path, kind
        raise HTTPException(status_code=404, detail="backup not found")

    @router.get("/ops/backups")
    def list_backups() -> dict:
        items = [backup_metadata(path, kind) for path, kind in _backup_paths()]
        return {"items": sorted(items, key=lambda item: item["name"], reverse=True)}

    @router.get("/ops/backups/{name}")
    def download_backup(name: str):
        path, _ = _find_backup(name)
        return FileResponse(
            str(path), filename=path.name, media_type="application/octet-stream"
        )

    @router.delete("/ops/backups/{name}")
    def delete_backup(name: str) -> dict:
        path, kind = _find_backup(name)
        path.unlink()
        logger.info("backup %s deleted via web", name)
        return {"ok": True, "kind": kind}

    def _pause_queue_for_restart(request: Request) -> None:
        """数据库即将被替换：暂停队列，避免旧内存状态继续写新库。"""
        queue = getattr(request.app.state, "queue", None)
        if queue is not None and not queue.is_paused():
            queue.pause()
            logger.warning(
                "数据库已被 Web 操作替换，队列已暂停；请尽快重启程序使各组件状态一致"
            )

    @router.post("/ops/restore")
    def restore_ops(body: dict, request: Request) -> dict:
        backup_path, kind = _find_backup(body.get("name"))
        if kind == "database":
            try:
                validate_database_backup(backup_path)
            except (ValueError, sqlite3.Error) as exc:
                raise HTTPException(
                    status_code=400, detail=f"backup invalid: {exc}"
                ) from exc
            _pause_queue_for_restart(request)
            backup_database(Path(ctx.database_path))
            source = sqlite3.connect(backup_path)
            target = sqlite3.connect(ctx.database_path)
            try:
                source.backup(target)
            finally:
                target.close()
                source.close()
        else:
            backup_config(Path(ctx.config_path))
            shutil.copy2(backup_path, ctx.config_path)
        return {"ok": True, "kind": kind, "restart_required": True}

    @router.post("/ops/import")
    async def import_ops(request: Request, kind: str) -> dict:
        destination = Path(ctx.config_path) if kind == "config" else Path(ctx.database_path)
        try:
            await import_backup(request.stream(), destination, kind)
        except (OSError, ValueError, sqlite3.Error) as exc:
            raise HTTPException(status_code=400, detail=f"backup import failed: {exc}") from exc
        if kind == "database":
            _pause_queue_for_restart(request)
        return {"ok": True, "kind": kind, "restart_required": True}

    @router.post("/ops/backup")
    def backup_ops(body: dict) -> dict:
        kind = body.get("kind")
        path = Path(ctx.config_path)
        if kind == "config":
            result = backup_config(path)
        elif kind == "database":
            result = backup_database(Path(ctx.database_path))
        else:
            raise HTTPException(status_code=400, detail="invalid backup kind")
        return {"backup": backup_metadata(result, kind)}

    @router.post("/ops/reset-database")
    def reset_database_ops(body: dict, request: Request) -> dict:
        if body.get("confirm") != "RESET DATABASE":
            raise HTTPException(status_code=400, detail="confirmation required")
        backup_database(Path(ctx.database_path))
        _pause_queue_for_restart(request)
        try:
            reset_database(Path(ctx.database_path))
        except sqlite3.Error as exc:
            raise HTTPException(status_code=500, detail="database reset failed") from exc
        return {"ok": True, "restart_required": True}

    return router
