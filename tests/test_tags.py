"""Tag 规范化、提取、合并去重与渲染。"""

from __future__ import annotations

from app.tags.engine import extract_hashtags, merge_tags, normalize_tags, render_tags


def test_normalize_space_separated():
    assert normalize_tags("#游戏 #GTA5 #MOD") == ["游戏", "GTA5", "MOD"]


def test_normalize_comma_and_chinese_separators():
    assert normalize_tags("游戏，GTA5,MOD") == ["游戏", "GTA5", "MOD"]
    assert normalize_tags("游戏 GTA5") == ["游戏", "GTA5"]


def test_normalize_concatenated_hashtags():
    assert normalize_tags("#游戏#GTA5") == ["游戏", "GTA5"]


def test_normalize_empty_and_none():
    assert normalize_tags("") == []
    assert normalize_tags(None) == []


def test_normalize_deduplicates_preserving_order():
    assert normalize_tags("游戏 游戏 GTA5") == ["游戏", "GTA5"]


def test_extract_hashtags_from_text():
    text = "GTA5 NVE 教程 #GTA5 #MOD 不错"
    assert extract_hashtags(text) == ["GTA5", "MOD"]


def test_merge_tags_deduplicates():
    source = ["游戏"]
    original = ["游戏", "GTA5"]
    manual = ["游戏", "MOD", "GTA5"]
    assert merge_tags(source, original, manual) == ["游戏", "GTA5", "MOD"]


def test_render_tags_space_separated():
    assert render_tags(["游戏", "GTA5", "MOD"]) == "#游戏 #GTA5 #MOD"
