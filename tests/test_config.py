"""Config 加载与缺失配置报错。"""

from __future__ import annotations

import pytest

from app.config import ConfigError, load_config


@pytest.fixture
def env(monkeypatch):
    monkeypatch.setenv("TELEGRAM_API_ID", "123456")
    monkeypatch.setenv("TELEGRAM_API_HASH", "testhash")
    return monkeypatch


def _write_config(tmp_path, text: str) -> str:
    path = tmp_path / "config.yaml"
    path.write_text(text, encoding="utf-8")
    return str(path)


MINIMAL = """
telegram:
  source_chats:
    - chat_id: -1001
      name: 游戏
      default_tags: [游戏]
  target_channel:
    chat_id: -1002
forward:
  interval: 3
admins:
  - 111
  - 222
"""

NO_SOURCE = """
telegram:
  target_channel:
    chat_id: -1002
"""


def test_load_minimal_config(env, tmp_path):
    cfg = load_config(_write_config(tmp_path, MINIMAL))
    assert cfg.api_id == 123456
    assert cfg.api_hash == "testhash"
    assert cfg.source_chats[0].chat_id == -1001
    assert cfg.source_chats[0].default_tags == ["游戏"]
    assert cfg.target_channel_id == -1002
    assert cfg.forward_interval == 3
    assert cfg.relay_chat_id is None
    assert cfg.admins == frozenset({111, 222})


def test_load_relay_chat(env, tmp_path):
    yaml_text = """
telegram:
  source_chats:
    - chat_id: -1001
      name: 游戏
  target_channel:
    chat_id: -1002
  relay_chat:
    chat_id: -1003
admins:
  - 111
"""
    cfg = load_config(_write_config(tmp_path, yaml_text))
    assert cfg.relay_chat_id == -1003


def test_missing_env_raises(monkeypatch, tmp_path):
    monkeypatch.delenv("TELEGRAM_API_ID", raising=False)
    monkeypatch.delenv("TELEGRAM_API_HASH", raising=False)
    monkeypatch.delenv("ADMIN_IDS", raising=False)
    with pytest.raises(ConfigError, match="TELEGRAM_API_ID"):
        load_config(_write_config(tmp_path, MINIMAL))


def test_empty_source_chats_raises(env, tmp_path):
    with pytest.raises(ConfigError, match="source_chats"):
        load_config(_write_config(tmp_path, NO_SOURCE))


def test_missing_admins_raises(env, tmp_path):
    with pytest.raises(ConfigError, match="admins"):
        load_config(_write_config(tmp_path, MINIMAL.replace("admins:\n  - 111\n  - 222\n", "")))
