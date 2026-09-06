"""运维端点：备份列举/下载/删除、恢复/导入/创建、重置数据库、导出。"""

from __future__ import annotations

import csv
import io
import json
import logging
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse

from app.task_failures import recent_failures
from app.web import queries
from app.web.backup import (
    backup_config,
    backup_database,
    backup_metadata,
    import_backup,
    reset_database,
    validate_database_backup,
)
from app.web.routes.deps import WebContext
from app.web.serializers import serialize_materials

logger = logging.getLogger(__name__)

# 导出分批拉取序列化，避免大库一次性载入；行数上限内整体构建（个人归档规模可控）
_EXPORT_BATCH = 500
_EXPORT_CAP = 20000

# CSV 列：表头用中文（与界面词汇一致），取值函数对应序列化后的素材 dict
_EXPORT_COLUMNS = [
    ("编号", lambda m: m["id"]),
    ("标题", lambda m: _export_title(m)),
    ("正文", lambda m: m["original_text"]),
    ("类型", lambda m: m["media_type"]),
    ("评分", lambda m: m["rating"]),
    ("状态", lambda m: m["status"]),
    ("标签", lambda m: " ".join(f"#{t['name']}" for t in m["tags"])),
    ("文件名", lambda m: m["file_name"]),
    ("归档链接", lambda m: m["target_url"] or ""),
    ("来源链接", lambda m: m["source_url"] or ""),
    ("频道", lambda m: (m["targets"] or [{}])[0].get("name", "")),
    ("归档时间", lambda m: m["created_at"]),
]


def _export_title(m: dict) -> str:
    """标题：正文首个非空行；退回文件名 / #编号（与列表标题口径一致）。"""
    for line in (m["original_text"] or "").splitlines():
        line = line.strip()
        if line:
            return line
    return m["file_name"] or f"#{m['id']}"


def _export_rows(request: Request, ctx: WebContext, status: str) -> list[dict]:
    """按 /messages 同款过滤条件分批序列化全部素材（超出上限截断）。"""
    items: list[dict] = []
    with queries.open_connection(ctx.database_path) as conn:
        offset = 0
        while offset < _EXPORT_CAP:
            limit = min(_EXPORT_BATCH, _EXPORT_CAP - offset)
            try:
                total, page = queries._query_materials(
                    conn, request.query_params, status, limit, offset, joined=True
                )
            except sqlite3.OperationalError as exc:
                if "no such table: message_targets" not in str(exc):
                    raise
                total, page = queries._query_materials(
                    conn, request.query_params, status, limit, offset, joined=False
                )
            if not page:
                break
            items.extend(serialize_materials(conn, page, ctx.target_names))
            offset += len(page)
            if offset >= total:
                break
    if offset >= _EXPORT_CAP:
        logger.info("export truncated at cap %s", _EXPORT_CAP)
    return items


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

    @router.get("/ops/failures")
    def list_failures(limit: int = 20) -> dict:
        """最近的后台任务失败记录（设置页「最近失败」面板；limit 收敛 1..50）。"""
        return {
            "items": recent_failures(
                ctx.database_path, limit=max(1, min(50, limit))
            )
        }

    @router.get("/ops/export")
    def export_ops(request: Request, format: str = "csv", status: str = "active"):
        """导出归档为 CSV/JSON：支持 /messages 同款过滤参数，超出上限截断。"""
        if format not in ("csv", "json"):
            raise HTTPException(status_code=400, detail="invalid format; expected csv or json")
        if status not in {"active", "deleted", "all"}:
            raise HTTPException(status_code=400, detail="invalid status")
        items = _export_rows(request, ctx, status)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        if format == "csv":
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow([header for header, _ in _EXPORT_COLUMNS])
            for m in items:
                writer.writerow([get(m) for _, get in _EXPORT_COLUMNS])
            # UTF-8 带 BOM：Excel 直接打开中文不乱码
            payload = b"\xef\xbb\xbf" + output.getvalue().encode("utf-8")
            filename = f"archive-export-{stamp}.csv"
            media_type = "text/csv; charset=utf-8"
        else:
            payload = json.dumps(
                {
                    "exported_at": datetime.now().astimezone().isoformat(timespec="seconds"),
                    "items": items,
                },
                ensure_ascii=False,
                default=str,
            ).encode("utf-8")
            filename = f"archive-export-{stamp}.json"
            media_type = "application/json; charset=utf-8"
        return StreamingResponse(
            iter([payload]),
            media_type=media_type,
            headers={
                # filename* 携带 UTF-8 文件名（RFC 5987），filename 为 ASCII 兜底
                "Content-Disposition": (
                    f"attachment; filename={filename}; filename*=UTF-8''{filename}"
                ),
                "X-Export-Count": str(len(items)),
            },
        )

    @router.get("/ops/backups/{name}")
    def download_backup(name: str):
        path, _ = _find_backup(name)
        return FileResponse(
            str(path), filename=path.name, media_type="application/octet-stream"
        )

    @router.post("/ops/backups/run")
    async def run_backup_now(request: Request) -> dict:
        """立即备份一次（本地落盘 + 按配置可选上传）；设置页「立即备份」用。

        常驻进程走 AutoBackupScheduler.run_once（复用校验/上传/保留清理）；
        devserver 等无调度器场景回退纯本地备份。"""
        scheduler = getattr(request.app.state, "auto_backup", None)
        if scheduler is not None:
            path = await scheduler.run_once()
        else:
            path = backup_database(Path(ctx.database_path))
            validate_database_backup(path)
        if path is None:
            raise HTTPException(status_code=500, detail="backup failed, see logs")
        logger.info("backup %s created via web (manual run)", path.name)
        return {"ok": True, "name": path.name}

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
