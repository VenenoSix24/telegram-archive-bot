"""配置端点：GET/PUT /config（config.yaml 的可编辑子集）。"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException

from app.telegram.client import resolve_chat_name
from app.web.config_editor import apply_editable_config, read_editable_config
from app.web.routes.deps import WebContext


def build_router(ctx: WebContext) -> APIRouter:
    router = APIRouter()

    @router.get("/config")
    async def get_config() -> dict:
        try:
            result = read_editable_config(Path(ctx.config_path))
            if ctx.client is not None:
                for collection in (result["source_chats"], result["target_channels"]):
                    for item in collection:
                        if not item.get("name") and item.get("chat_id") is not None:
                            try:
                                item["name"] = await resolve_chat_name(ctx.client, item["chat_id"])
                            except Exception:
                                pass
            return result
        except Exception as exc:
            raise HTTPException(status_code=400, detail="config.yaml unreadable") from exc

    @router.put("/config")
    def put_config(body: dict) -> dict:
        try:
            return apply_editable_config(Path(ctx.config_path), dict(body))
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"config invalid: {exc}") from exc

    return router
