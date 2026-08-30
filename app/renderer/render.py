"""最终消息渲染：评级 → Tag → 正文 → 来源。

格式顺序固定（文档第 10 节）。Render 只在数据库记录 original_text，
改模板可重新生成 rendered_text（文档第 35 节）。
"""

from __future__ import annotations

from app.tags.engine import render_tags


def format_rating(rating: int) -> str:
    """评级 0~5，0 或越界返回空串，1~5 对应 ⭐×N。"""
    if 1 <= rating <= 5:
        return "⭐" * rating
    return ""


def render_message(
    *,
    rating: int,
    tags: list[str],
    body: str,
    source_url: str | None,
) -> str:
    """按固定顺序组装最终频道消息文本；空段落自动省略。"""
    lines: list[str] = []
    stars = format_rating(rating)
    tag_line = render_tags(tags)
    if stars:
        lines.append(stars)
    if tag_line:
        lines.append(tag_line)
    if body:
        if lines:
            lines.append("")
        lines.append(body)
    if source_url:
        if lines:
            lines.append("")
        lines.append("来自：")
        lines.append(source_url)
    return "\n".join(lines)
