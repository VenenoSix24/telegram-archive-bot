"""Tag 提取、规范化、合并去重与渲染。

规范化规则：任何输入（#游戏 / 游戏,GTA5 / 游戏，GTA5，MOD / /tag 游戏 MOD）
都统一成 ['游戏', 'GTA5', 'MOD']；渲染时每个 Tag 前加 #、用空格连接，
不换行、不连写——连续 hashtag 会被 Telegram 识别成单个。
"""

from __future__ import annotations

import re

_SEPARATOR_RE = re.compile(r"[#,\s、，]+")


def normalize_tags(raw: str | None) -> list[str]:
    """从任意原始输入规范化出 tag 列表（无 #、按任意分隔符拆分、去重保序）。"""
    if not raw:
        return []
    parts = [p.strip() for p in _SEPARATOR_RE.split(raw) if p.strip()]
    return list(dict.fromkeys(parts))


def extract_hashtags(text: str | None) -> list[str]:
    """从正文提取原始 hashtag（如 #GTA5），不包含 # 前缀。"""
    if not text:
        return []
    found = re.findall(r"#([^\s#]+)", text)
    return list(dict.fromkeys(found))


def merge_tags(*groups: list[str]) -> list[str]:
    """多个来源的 tag 合并去重，保持首次出现的顺序。"""
    merged: list[str] = []
    for group in groups:
        for tag in group:
            if tag and tag not in merged:
                merged.append(tag)
    return merged


def render_tags(tags: list[str]) -> str:
    """渲染为 '#游戏 #GTA5 #MOD'。"""
    return " ".join(f"#{tag}" for tag in tags)
