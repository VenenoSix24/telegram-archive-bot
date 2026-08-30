"""MessageAdapter：媒体分类与标准化字段提取。"""

from __future__ import annotations

from types import SimpleNamespace

from app.processor.adapter import build_incoming, build_source_url, classify_media


def _msg(text="", media=None, grouped_id=None, mid=7):
    return SimpleNamespace(id=mid, message=text, media=media, grouped_id=grouped_id)


def test_build_source_url_with_username():
    chat = SimpleNamespace(username="my_channel")
    assert build_source_url(chat, 12) == "https://t.me/my_channel/12"


def test_build_source_url_private_channel_deeplink():
    chat = SimpleNamespace(username=None, id=-1003942965645)
    assert build_source_url(chat, 12) == "https://t.me/c/3942965645/12"


def test_build_source_url_plain_group_none():
    assert build_source_url(SimpleNamespace(username=None, id=123456), 12) is None


def test_classify_media_none():
    assert classify_media(None) is None


def test_build_incoming_text_and_group():
    inc = build_incoming(_msg(text="hi", grouped_id="group123"), -1001, "https://t.me/x/7")
    assert inc.source_chat_id == -1001
    assert inc.source_message_id == 7
    assert inc.text == "hi"
    assert inc.media_type is None
    assert inc.media_group_id == "group123"
    assert inc.source_url == "https://t.me/x/7"
