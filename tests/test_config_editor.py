"""Settings 配置编辑器：白名单读写 + 原子写 + 备份。"""

from __future__ import annotations

from pathlib import Path

from app.web.config_editor import apply_editable_config, read_editable_config

CONFIG = """# 注释应被保留
telegram:
  source_chats:
    - chat_id: -1001
      name: 游戏
      default_tags: [游戏]
  target_channel:
    chat_id: -1002
forward:
  interval: 3
source:
  show_link: true
tags:
  preserve_original: true
rating:
  enabled: true
search:
  url_template: null
admins:
  - 111
"""


def _write(tmp_path: Path) -> Path:
    p = tmp_path / "config.yaml"
    p.write_text(CONFIG, encoding="utf-8")
    return p


def test_read_editable_config(tmp_path):
    p = _write(tmp_path)
    cfg = read_editable_config(p)
    assert cfg["source_chats"][0]["chat_id"] == -1001
    assert cfg["target_channels"] == [{"chat_id": -1002, "name": "", "private": False}]
    assert cfg["target_channel_id"] == -1002
    assert cfg["target_channel_id"] == -1002
    assert cfg["forward_interval"] == 3
    assert cfg["admins"] == [111]
    # 凭据字段不暴露
    assert "api_id" not in cfg


def test_apply_multiple_targets(tmp_path):
    p = _write(tmp_path)
    targets = [
        {"chat_id": -1002, "name": "A", "private": True},
        {"chat_id": -1003, "name": "B", "private": True},
    ]
    new = apply_editable_config(p, {"target_channels": targets})
    assert new["target_channels"] == targets



    p = _write(tmp_path)
    new = apply_editable_config(p, {"forward_interval": 5, "admins": [111, 222]})
    assert new["forward_interval"] == 5
    assert new["admins"] == [111, 222]
    # 备份留存
    assert p.with_suffix(".yaml.bak").exists()


def test_apply_ignores_unknown_keys(tmp_path):
    p = _write(tmp_path)
    new = apply_editable_config(p, {"not_a_field": 1})
    assert "not_a_field" not in new


def test_apply_preserves_comment(tmp_path):
    p = _write(tmp_path)
    apply_editable_config(p, {"forward_interval": 7})
    text = p.read_text(encoding="utf-8")
    assert "注释应被保留" in text
    assert "interval: 7" in text
