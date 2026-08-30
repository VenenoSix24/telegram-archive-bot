"""Renderer 输出格式与顺序。"""

from __future__ import annotations

from app.renderer.render import format_rating, render_message


def test_format_rating():
    assert format_rating(5) == "⭐⭐⭐⭐⭐"
    assert format_rating(1) == "⭐"
    assert format_rating(0) == ""
    assert format_rating(6) == ""


def test_render_full_message():
    text = render_message(
        rating=5,
        tags=["游戏", "GTA5", "MOD"],
        body="GTA5 NVE 教程",
        source_url="https://t.me/xxx/123",
    )
    assert text == (
        "⭐⭐⭐⭐⭐\n"
        "#游戏 #GTA5 #MOD\n"
        "\n"
        "GTA5 NVE 教程\n"
        "\n"
        "来自：\n"
        "https://t.me/xxx/123"
    )


def test_render_omits_empty_sections():
    text = render_message(rating=0, tags=[], body="", source_url=None)
    assert text == ""


def test_render_no_rating_no_tags():
    text = render_message(
        rating=0, tags=[], body="只有正文", source_url="https://t.me/xxx/1"
    )
    assert text == "只有正文\n\n来自：\nhttps://t.me/xxx/1"


def test_render_no_source_link():
    text = render_message(rating=4, tags=["游戏"], body="正文", source_url=None)
    assert text == "⭐⭐⭐⭐\n#游戏\n\n正文"
