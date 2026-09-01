"""Config 加载与缺失配置报错。"""

from __future__ import annotations

import pytest

from app.config import ConfigError, load_config


@pytest.fixture
def env(monkeypatch):
    monkeypatch.setenv("TELEGRAM_API_ID", "123456")
    monkeypatch.setenv("TELEGRAM_API_HASH", "testhash")
    monkeypatch.setenv("WEB_TOKEN", "test-web-token")
    return monkeypatch


@pytest.fixture(autouse=True)
def _block_dotenv(monkeypatch):
    """阻止 load_config 读到真实 .env（find_dotenv 会向上找父目录）。"""
    monkeypatch.setattr("app.config.load_dotenv", lambda: None)


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
    assert cfg.admins == frozenset({111, 222})


def test_load_template_layout(env, tmp_path):
    cfg = load_config(_write_config(
        tmp_path,
        MINIMAL + "\nmessage_template: [body, tags]\n",
    ))
    assert cfg.message_template == ["body", "tags"]

def test_legacy_relay_chat_merged_as_source(env, tmp_path):
    yaml_text = """
telegram:
  source_chats:
    - chat_id: -1001
      name: 游戏
  target_channel:
    chat_id: -1002
  relay_chat:
    chat_id: -1003
    default_tags: [历史]
admins:
  - 111
"""
    cfg = load_config(_write_config(tmp_path, yaml_text))
    ids = {c.chat_id for c in cfg.source_chats}
    assert ids == {-1001, -1003}
    relay = next(c for c in cfg.source_chats if c.chat_id == -1003)
    assert relay.default_tags == ["历史"]


def test_target_for_override_and_default(env, tmp_path):
    yaml_text = """
telegram:
  source_chats:
    - chat_id: -1001
      name: 游戏
      target_channel_id: -1008
    - chat_id: -1002
      name: 软件
  target_channel:
    chat_id: -1009
admins:
  - 1
"""
    cfg = load_config(_write_config(tmp_path, yaml_text))
    assert cfg.target_for(-1001) == -1008
    assert cfg.target_for(-1002) == -1009
    assert cfg.all_target_channel_ids() == {-1008, -1009}


def test_load_multiple_targets(env, tmp_path):
    yaml_text = """
telegram:
  source_chats:
    - chat_id: -1001
      name: 游戏
      target_channel_ids: [-1008, -1009]
  target_channels:
    - chat_id: -1008
      name: 频道 A
    - chat_id: -1009
      name: 频道 B
admins:
  - 1
"""
    cfg = load_config(_write_config(tmp_path, yaml_text))
    assert cfg.targets_for(-1001) == [-1008, -1009]
    assert cfg.all_target_channel_ids() == {-1008, -1009}


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


def test_web_token_required_when_enabled(env, tmp_path, monkeypatch):
    monkeypatch.setenv("WEB_ENABLED", "true")
    monkeypatch.delenv("WEB_TOKEN", raising=False)
    with pytest.raises(ConfigError, match="WEB_TOKEN"):
        load_config(_write_config(tmp_path, MINIMAL))


def test_web_disabled_skips_token(env, tmp_path, monkeypatch):
    monkeypatch.setenv("WEB_ENABLED", "false")
    monkeypatch.delenv("WEB_TOKEN", raising=False)
    cfg = load_config(_write_config(tmp_path, MINIMAL))
    assert cfg.web_enabled is False


def test_web_parses_env(env, tmp_path):
    cfg = load_config(_write_config(tmp_path, MINIMAL))
    assert cfg.web_enabled is True
    assert cfg.web_token == "test-web-token"
    assert cfg.web_host == "127.0.0.1"
    assert cfg.web_port == 8000
