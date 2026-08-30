"""管理命令解析。"""

from __future__ import annotations

from app.processor.commands import parse_command


def test_parse_rating_with_value():
    assert parse_command("/rating 5") == ("rating", ["5"])


def test_parse_rating_with_bot_suffix():
    assert parse_command("/rating@MyBot 3") == ("rating", ["3"])


def test_parse_tag_multiple_args():
    assert parse_command("/tag GTA5 MOD 画质") == ("tag", ["GTA5", "MOD", "画质"])


def test_parse_status_no_args():
    assert parse_command("/status") == ("status", [])


def test_parse_plain_text_not_command():
    assert parse_command("GTA5 NVE 教程") is None


def test_parse_unknown_command():
    assert parse_command("/hack 1") is None


def test_parse_empty_and_none():
    assert parse_command("") is None
    assert parse_command(None) is None
