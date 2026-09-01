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
        "推荐指数：⭐⭐⭐⭐⭐\n"
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
    assert text == "推荐指数：⭐⭐⭐⭐\n#游戏\n\n正文"


def test_render_strips_hashtags_from_body():
    text = render_message(
        rating=0, tags=["游戏", "GTA5"], body="#GTA5 教程", source_url=None
    )
    assert text == "#游戏 #GTA5\n\n教程"


def test_render_body_folds_extra_spaces():
    text = render_message(rating=0, tags=["GTA5"], body="这是 #GTA5 教程", source_url=None)
    assert text == "#GTA5\n\n这是 教程"


def test_render_all_hashtags_body_omitted():
    text = render_message(rating=0, tags=["游戏"], body="#游戏", source_url=None)
    assert text == "#游戏"


def test_render_respects_saved_block_layout():
    text = render_message(
        rating=4,
        tags=["游戏"],
        body="正文",
        source_url="https://t.me/example/1",
        template_layout=["body", "rating"],
    )
    assert text == "正文\n\n推荐指数：⭐⭐⭐⭐"
