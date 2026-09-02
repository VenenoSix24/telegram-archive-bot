"""素材端点：列表/详情/编辑（GET /messages, PATCH /messages/{id}）。"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app.processor.edit import apply_message_edit
from app.web import queries
from app.web.routes.deps import WebContext
from app.web.serializers import apply_target_names, expand_target, serialize_message


class PatchBody(BaseModel):
    target_id: int | None = None
    body: str | None = None
    body_html: str | None = None
    add_tags: list[str] | None = None
    remove_tag_names: list[str] | None = None
    rating: int | None = Field(default=None, ge=0, le=5)


def build_router(ctx: WebContext) -> APIRouter:
    router = APIRouter()

    @router.get("/messages")
    def list_messages(
        request: Request, limit: int = 30, offset: int = 0, status: str = "active"
    ) -> dict:
        if status not in {"active", "deleted", "all"}:
            raise HTTPException(status_code=400, detail="invalid status")
        with queries.open_connection(ctx.database_path) as conn:
            return queries.list_messages(
                conn,
                request.query_params,
                status=status,
                limit=limit,
                offset=offset,
                target_names=ctx.target_names,
            )

    @router.get("/messages/{message_id}")
    def get_message(message_id: int) -> dict:
        with queries.open_connection(ctx.database_path) as conn:
            row = queries.get_message_row(conn, message_id)
            if row is None:
                raise HTTPException(status_code=404, detail="message not found")
            return apply_target_names(serialize_message(conn, row), ctx.target_names)

    @router.patch("/messages/{message_id}")
    async def patch_message(message_id: int, request: Request, body: PatchBody) -> dict:
        if (
            body.add_tags is None
            and body.remove_tag_names is None
            and body.rating is None
            and body.body is None
            and body.body_html is None
        ):
            raise HTTPException(status_code=422, detail="nothing to change")
        client = request.app.state.client
        conn = request.app.state.conn
        indexer = request.app.state.indexer
        if client is None or conn is None:
            raise HTTPException(status_code=503, detail="telegram client not available")
        ok = await apply_message_edit(
            client,
            conn,
            message_id,
            target_id=body.target_id,
            body=body.body,
            body_html=body.body_html,
            add_tags=body.add_tags,
            remove_tag_names=body.remove_tag_names,
            rating=body.rating,
            indexer=indexer,
        )
        if not ok:
            raise HTTPException(status_code=404, detail="message not found or not archived")
        with queries.open_connection(ctx.database_path) as db:
            row = queries.get_message_row(db, message_id)
            message = apply_target_names(serialize_message(db, row), ctx.target_names)
            if body.target_id is None:
                return message
            target = next(
                (item for item in message["targets"] if item["id"] == body.target_id),
                None,
            )
            if target is None:
                raise HTTPException(status_code=404, detail="target not found")
            return expand_target(message, target)

    return router
