"""统一编辑服务：tag/rating/body 变更 → DB 双写 → edit 目标消息。

verify 双向同步的唯一入口（Telegram 命令与 Web API 均走这里）。

E3 收敛：父表（messages/message_tags）与副本（message_targets/target_tags）
的双写此前散在两条互不相通的路径上——父级路径只写父表、副本路径只写副
本表，父表与副本就此分叉（如源群 /rating 更新了全部副本、父表 rating 仍
是 0；Web 无 target_id 的编辑只改父表、副本原地不动）。现在统一由
MessageEditService 持有全部写路径：

- target_id=None（源级编辑）：写父表 + 镜像到全部归档副本（各自按副本
  正文/骨架重渲染并 edit 对应 Telegram 消息）；无副本的旧数据回退父级
  遗留目标消息。
- target_id=N（副本级编辑）：只写该副本（独立副本模型，TG 改哪条同步哪条）。
"""

from __future__ import annotations

import html as html_lib
import json
import logging
import re
import sqlite3

from telethon.errors import MessageNotModifiedError

from app.processor.ratings import update_rating
from app.processor.recorder import add_manual_tags, remove_tags
from app.renderer.render import render_message
from app.tags.engine import render_tags

logger = logging.getLogger(__name__)

_RATING_LINE_RE = re.compile(r"^推荐指数：⭐+$")


async def _telegram_edit(client, chat_id: int, message_id: int, rendered: str) -> None:
    try:
        await client.edit_message(chat_id, message_id, rendered, parse_mode="html")
    except MessageNotModifiedError:
        # 内容本就一致（如重复添加已有 Tag / 相同评级），视为成功
        pass
    except TypeError as exc:
        if "parse_mode" not in str(exc):
            raise
        await client.edit_message(chat_id, message_id, rendered)


def extract_edited_body(
    text: str, html_text: str, *, tags: list[str], source_url: str | None
) -> tuple[str, str]:
    """从 Telegram 编辑后的整条渲染消息中剥离模板骨架，只留正文。

    用户编辑的是「评级+Tag+正文+来源」的完整渲染结果，直接当正文回写会
    套娃。编辑习惯不可假设：可能在末尾追加（来源块之后）、也可能残留上
    一轮失败产生的脏骨架，因此骨架按内容精确匹配、全文任意位置移除——
    评级行允许星数增减，来源块兼容 Telegram 自动加链接实体后的 <a> 形态。
    代价：正文里恰好整行等于骨架的罕见内容会被一并移除。
    """
    plain_tag_line = render_tags(tags) if tags else ""
    html_tag_line = html_lib.escape(plain_tag_line) if tags else ""
    url_variants: set[str] = set()
    if source_url:
        escaped_url = html_lib.escape(source_url, quote=True)
        url_variants = {
            source_url,
            escaped_url,
            f'<a href="{escaped_url}">{escaped_url}</a>',
            f'<a href="{source_url}">{source_url}</a>',
        }

    def clean(lines: list[str], *, html: bool) -> list[str]:
        tag_line = html_tag_line if html else plain_tag_line
        kept: list[str] = []
        index = 0
        while index < len(lines):
            line = lines[index]
            if _RATING_LINE_RE.match(line) or (tag_line and line == tag_line):
                index += 1
                continue
            if (
                source_url
                and line == "来自："
                and index + 1 < len(lines)
                and lines[index + 1] in url_variants
            ):
                index += 2
                continue
            kept.append(line)
            index += 1
        # 折叠连续空行（移除骨架后遗留），再掐头去尾
        collapsed: list[str] = []
        for line in kept:
            if line == "" and (not collapsed or collapsed[-1] == ""):
                continue
            collapsed.append(line)
        while collapsed and collapsed[0] == "":
            collapsed.pop(0)
        while collapsed and collapsed[-1] == "":
            collapsed.pop()
        return collapsed

    body = "\n".join(clean(text.split("\n"), html=False)).strip()
    body_html = "\n".join(clean(html_text.split("\n"), html=True)).strip()
    return body, body_html


class MessageEditService:
    """父表/副本双写的统一编辑服务（E3）。

    所有编辑（Telegram 回复指令、目标事件、Web PATCH）都收敛到 apply()；
    返回是否有实际变更（False = 无变化或不可编辑）。
    """

    def __init__(self, client, conn: sqlite3.Connection, indexer=None):
        self._client = client
        self._conn = conn
        self._indexer = indexer

    async def apply(
        self,
        message_id: int,
        *,
        target_id: int | None = None,
        body: str | None = None,
        body_html: str | None = None,
        add_tags: list[str] | None = None,
        remove_tag_names: list[str] | None = None,
        rating: int | None = None,
    ) -> bool:
        """应用一次编辑；target_id 缺省为源级（父表 + 全部副本）。"""
        parent = self._conn.execute(
            "SELECT * FROM messages WHERE id=?", (message_id,)
        ).fetchone()
        if parent is None or not parent["target_chat_id"]:
            return False
        if target_id is None:
            return await self._apply_source_level(
                parent,
                body=body,
                body_html=body_html,
                add_tags=add_tags,
                remove_tag_names=remove_tag_names,
                rating=rating,
            )
        return await self._apply_copy(
            parent,
            target_id,
            body=body,
            body_html=body_html,
            add_tags=add_tags,
            remove_tag_names=remove_tag_names,
            rating=rating,
        )

    # -- 源级编辑：父表 + 全部归档副本 ----------------------------------

    async def _apply_source_level(
        self,
        parent,
        *,
        body: str | None,
        body_html: str | None,
        add_tags: list[str] | None,
        remove_tag_names: list[str] | None,
        rating: int | None,
    ) -> bool:
        del body, body_html  # 正文属于副本内容，源级编辑只管共享的 tag/rating
        if not (add_tags or remove_tag_names or rating is not None):
            return False
        rendered = None
        if add_tags:
            rendered = add_manual_tags(self._conn, parent["id"], add_tags)
        if remove_tag_names:
            rendered = remove_tags(self._conn, parent["id"], remove_tag_names)
        if rating is not None:
            rendered = update_rating(self._conn, parent["id"], rating)
        parent_changed = rendered is not None
        copies = self._archived_copies(parent["id"])
        changed = parent_changed
        failed = False
        for copy in copies:
            try:
                copy_rendered = self._mirror_to_copy(
                    parent,
                    copy,
                    add_tags=add_tags,
                    remove_tag_names=remove_tag_names,
                    rating=rating,
                )
            except Exception:
                logger.exception(
                    "source edit mirror failed for messages#%s target#%s",
                    parent["id"], copy["id"],
                )
                failed = True
                continue
            if copy_rendered is not None:
                await _telegram_edit(
                    self._client, copy["target_chat_id"], copy["target_message_id"],
                    copy_rendered,
                )
                changed = True
        if parent_changed and not copies:
            # 无副本的旧数据：编辑父级遗留目标消息；有副本时父级消息即副本
            # 的 Telegram 消息，由上面的镜像路径编辑，避免父级内容覆盖副本正文
            await _telegram_edit(
                self._client, parent["target_chat_id"], parent["target_message_id"],
                rendered,
            )
        if changed and not failed and self._indexer is not None:
            self._indexer.schedule()
        return changed and not failed

    def _archived_copies(self, message_id: int) -> list:
        try:
            return self._conn.execute(
                "SELECT * FROM message_targets WHERE message_id=? AND status='archived' "
                "ORDER BY id",
                (message_id,),
            ).fetchall()
        except sqlite3.OperationalError as exc:
            if "no such table: message_targets" not in str(exc):
                raise
            return []

    def _mirror_to_copy(
        self,
        parent,
        copy,
        *,
        add_tags: list[str] | None,
        remove_tag_names: list[str] | None,
        rating: int | None,
    ) -> str | None:
        """把源级 tag/rating 变更镜像到一条副本；副本无变化返回 None。"""
        if not self._copy_would_change(copy, add_tags, remove_tag_names, rating):
            return None
        return self._write_copy(
            parent,
            copy,
            body=None,
            body_html=None,
            add_tags=add_tags,
            remove_tag_names=remove_tag_names,
            rating=rating,
        )

    def _copy_would_change(
        self,
        copy,
        add_tags: list[str] | None,
        remove_tag_names: list[str] | None,
        rating: int | None,
    ) -> bool:
        if rating is not None or remove_tag_names:
            return True
        if not add_tags:
            return False
        existing = {
            row["name"]
            for row in self._conn.execute(
                "SELECT t.name FROM target_tags tt JOIN tags t ON t.id=tt.tag_id "
                "WHERE tt.target_id=?",
                (copy["id"],),
            )
        }
        return any(name not in existing for name in add_tags)

    # -- 副本级编辑 ------------------------------------------------------

    async def _apply_copy(
        self,
        parent,
        target_id: int,
        *,
        body: str | None,
        body_html: str | None,
        add_tags: list[str] | None,
        remove_tag_names: list[str] | None,
        rating: int | None,
    ) -> bool:
        try:
            target = self._conn.execute(
                "SELECT * FROM message_targets WHERE id=? AND message_id=?",
                (target_id, parent["id"]),
            ).fetchone()
        except sqlite3.OperationalError as exc:
            if "no such table: message_targets" not in str(exc):
                raise
            return False
        if target is None or target["status"] != "archived":
            return False
        if not (add_tags or remove_tag_names or rating is not None or body is not None):
            return False
        rendered = self._write_copy(
            parent,
            target,
            body=body,
            body_html=body_html,
            add_tags=add_tags,
            remove_tag_names=remove_tag_names,
            rating=rating,
        )
        await _telegram_edit(
            self._client, target["target_chat_id"], target["target_message_id"], rendered
        )
        if self._indexer is not None:
            self._indexer.schedule()
        return True

    def _write_copy(
        self,
        parent,
        target,
        *,
        body: str | None,
        body_html: str | None,
        add_tags: list[str] | None,
        remove_tag_names: list[str] | None,
        rating: int | None,
    ) -> str:
        """写一条副本的 tag/rating/body 并重渲染，返回新 rendered_text。"""
        tags = [
            tag["name"]
            for tag in self._conn.execute(
                "SELECT t.name FROM target_tags tt JOIN tags t ON t.id=tt.tag_id "
                "WHERE tt.target_id=? ORDER BY tt.rowid",
                (target["id"],),
            )
        ]
        for name in add_tags or []:
            if name not in tags:
                self._conn.execute(
                    "INSERT OR IGNORE INTO tags (name, normalized_name) VALUES (?, ?)",
                    (name, name.lower()),
                )
                tag_row = self._conn.execute(
                    "SELECT id FROM tags WHERE name=?", (name,)
                ).fetchone()
                self._conn.execute(
                    "INSERT OR IGNORE INTO target_tags "
                    "(target_id, tag_id, type) VALUES (?, ?, 'manual')",
                    (target["id"], tag_row["id"]),
                )
                tags.append(name)
        if remove_tag_names:
            placeholders = ", ".join("?" for _ in remove_tag_names)
            self._conn.execute(
                f"DELETE FROM target_tags WHERE target_id=? AND tag_id IN "
                f"(SELECT id FROM tags WHERE name IN ({placeholders}))",
                [target["id"], *remove_tag_names],
            )
            tags = [tag for tag in tags if tag not in remove_tag_names]

        next_rating = rating if rating is not None else target["rating"]
        next_body = body if body is not None else target["original_text"]
        next_body_html = target["original_html"] if body is None else body_html
        try:
            template_layout = json.loads(target["template_layout"])
        except (IndexError, KeyError, TypeError, json.JSONDecodeError):
            template_layout = None
        rendered = render_message(
            rating=next_rating,
            tags=tags,
            body=next_body,
            body_html=next_body_html or None,
            source_url=parent["source_url"],
            template_layout=template_layout,
        )
        self._conn.execute(
            "UPDATE message_targets SET rating=?, original_text=?, original_html=?, "
            "rendered_text=? WHERE id=?",
            (next_rating, next_body, next_body_html or "", rendered, target["id"]),
        )
        self._conn.commit()
        return rendered


async def apply_message_edit(
    client,
    conn: sqlite3.Connection,
    message_id: int,
    *,
    target_id: int | None = None,
    body: str | None = None,
    body_html: str | None = None,
    add_tags: list[str] | None = None,
    remove_tag_names: list[str] | None = None,
    rating: int | None = None,
    indexer=None,
) -> bool:
    """兼容入口：构造 MessageEditService 并应用（所有调用方仍走这里）。"""
    service = MessageEditService(client, conn, indexer=indexer)
    return await service.apply(
        message_id,
        target_id=target_id,
        body=body,
        body_html=body_html,
        add_tags=add_tags,
        remove_tag_names=remove_tag_names,
        rating=rating,
    )
