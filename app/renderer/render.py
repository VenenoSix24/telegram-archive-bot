"""最终消息渲染：评级 → Tag → 正文 → 来源。

格式顺序固定（文档第 10 节）。original_text 存原文，渲染时正文剔除已并入
tag 区的 hashtag（避免与上方 tag 行重复），改模板可重新生成 rendered_text
（文档第 35 节）。
"""

from __future__ import annotations

import html as html_lib
import re
from collections.abc import Sequence

from app.tags.engine import render_tags

_DEFAULT_LAYOUT = ("rating", "tags", "body", "source")

_HASHTAG = re.compile(r"#[^\s#]+")


def format_rating(rating: int) -> str:
    """评级 0~5，0 或越界返回空串，1~5 对应 ⭐×N。"""
    if 1 <= rating <= 5:
        return "⭐" * rating
    return ""


def _strip_echoed_tags(text: str) -> str:
    """去掉正文中已并入 tag 区的 hashtag，折叠连续空格，保留换行。"""
    text = _HASHTAG.sub("", text)
    return re.sub(r"[ \t]+", " ", text).strip()


def _strip_echoed_tags_html(value: str, tags: list[str]) -> str:
    """Remove only tags present in the structured Tag section from HTML text."""
    if not tags:
        return value
    pattern = re.compile(r"#(?:" + "|".join(re.escape(tag.lstrip("#")) for tag in tags) + r")\b")
    parts = re.split(r"(<[^>]+>)", value)
    return "".join(
        part if part.startswith("<") else pattern.sub("", part)
        for part in parts
    )


def normalize_template_layout(layout: Sequence[str] | None) -> tuple[str, ...]:
    """Validate an archive layout snapshot, falling back to the legacy format."""
    if not isinstance(layout, Sequence) or isinstance(layout, str):
        return _DEFAULT_LAYOUT
    normalized = tuple(str(block) for block in layout)
    if (
        "body" not in normalized
        or len(normalized) != len(set(normalized))
        or any(block not in _DEFAULT_LAYOUT for block in normalized)
    ):
        return _DEFAULT_LAYOUT
    return normalized


def render_message(
    *,
    rating: int,
    tags: list[str],
    body: str,
    source_url: str | None,
    body_html: str | None = None,
    template_layout: Sequence[str] | None = None,
) -> str:
    """Render enabled blocks in a persisted layout snapshot."""
    blocks: dict[str, str] = {}
    stars = format_rating(rating)
    if stars:
        blocks["rating"] = f"推荐指数：{stars}"
    tag_line = html_lib.escape(render_tags(tags))
    if tag_line:
        blocks["tags"] = tag_line

    cleaned = (
        _strip_echoed_tags_html(body_html, tags)
        if body_html is not None
        else html_lib.escape(_strip_echoed_tags(body) if body else "")
    )
    if cleaned:
        blocks["body"] = cleaned

    if source_url:
        blocks["source"] = "来自：\n" + html_lib.escape(source_url, quote=True)
    return "\n\n".join(
        blocks[block] for block in normalize_template_layout(template_layout) if blocks.get(block)
    )
