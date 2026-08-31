"""Settings 配置文件的安全读取与更新。

读写只暴露白名单字段（源群/总频道/限速/开关/搜索模板/管理员），
凭据类（api_id/api_hash/web_token）不返回也不接收。用 ruamel round-trip
模式读写，保留 config.yaml 的用户注释与排版，避免编辑一次丢注释。
写前校验、写时备份、写后提示重启生效。
"""

from __future__ import annotations

import shutil
from io import StringIO
from pathlib import Path

from ruamel.yaml import YAML

# round-trip：加载与转储都能保住注释/键序
_yaml = YAML()
_yaml.preserve_quotes = True


def _read_raw(path: Path):
    """round-trip 加载；返回 ruamel CommentedMap，保留顶层注释与键序。"""
    if not path.exists():
        return _yaml.load("{}")  # 空文档返回 CommentedMap 便于后续 setdefault
    with path.open(encoding="utf-8") as fh:
        data = _yaml.load(fh)
    return data if data is not None else _yaml.load("{}")


def _bool(raw, default: bool) -> bool:
    if isinstance(raw, bool):
        return raw
    if raw is None:
        return default
    return str(raw).strip().lower() in ("1", "true", "yes", "on")


def read_editable_config(path: Path) -> dict:
    raw = _read_raw(path)
    tg = raw.get("telegram", {})
    src = raw.get("source", {})
    tags_cfg = raw.get("tags", {})
    rating = raw.get("rating", {})
    search = raw.get("search", {})
    fw = raw.get("forward", {})
    thumbs = raw.get("thumbnails", {})
    sync_target_edits = bool(raw.get("sync_target_edits", False))

    return {
        "source_chats": [
            {
                "chat_id": c.get("chat_id"),
                "name": c.get("name", ""),
                "private": bool(c.get("private", True)),
                "target_channel_ids": list(c.get("target_channel_ids", [])) or (
                    [c["target_channel_id"]]
                    if c.get("target_channel_id") is not None
                    else []
                ),
            }
            for c in tg.get("source_chats", [])
        ],
        "target_channels": [
            {
                "chat_id": c.get("chat_id"),
                "name": c.get("name", ""),
                "private": bool(c.get("private", True)),
            }
            for c in tg.get("target_channels", [])
        ] or ([
            {
                "chat_id": (tg.get("target_channel") or {}).get("chat_id"),
                "name": "",
                "private": False,
            }
        ] if (tg.get("target_channel") or {}).get("chat_id") is not None else []),
        "target_channel_id": (tg.get("target_channel") or {}).get("chat_id"),
        "forward_interval": fw.get("interval", 3),
        "retry_count": fw.get("retry_count", 3),
        "show_link": _bool(src.get("show_link"), True),
        "preserve_original": _bool(tags_cfg.get("preserve_original"), True),
        "rating_enabled": _bool(rating.get("enabled"), True),
        "url_template": search.get("url_template"),
        "admins": [int(a) for a in raw.get("admins", [])],
        "thumbnail_media": thumbs.get("media", "first_video"),
        "thumbnail_source": thumbs.get("source", "auto"),
        "sync_target_edits": sync_target_edits,
    }


def apply_editable_config(path: Path, edits: dict) -> dict:
    """把白名单变更合并写回 config.yaml（round-trip 保注释 + 备份一份）。

    只更新 edits 中出现的键；未知键直接忽略。
    """
    if path.exists():
        shutil.copy2(path, path.with_suffix(".yaml.bak"))

    current = read_editable_config(path)
    merged = {**current, **{k: v for k, v in edits.items() if k in current}}

    raw = _read_raw(path)
    tg = raw.setdefault("telegram", {})
    tg["source_chats"] = merged["source_chats"]
    tg["target_channels"] = merged["target_channels"]
    if not merged["target_channels"]:
        raise ValueError("至少需要一个目标频道")
    tg.pop("target_channel", None)
    raw.setdefault("forward", {})["interval"] = merged["forward_interval"]
    raw.setdefault("forward", {})["retry_count"] = merged["retry_count"]
    raw.setdefault("source", {})["show_link"] = merged["show_link"]
    raw.setdefault("tags", {})["preserve_original"] = merged["preserve_original"]
    raw.setdefault("rating", {})["enabled"] = merged["rating_enabled"]
    raw.setdefault("search", {})["url_template"] = merged["url_template"]
    raw["admins"] = merged["admins"]
    raw.setdefault("thumbnails", {})["media"] = merged["thumbnail_media"]
    raw.setdefault("thumbnails", {})["source"] = merged["thumbnail_source"]
    raw["sync_target_edits"] = merged["sync_target_edits"]

    buf = StringIO()
    _yaml.dump(raw, buf)
    path.write_text(buf.getvalue(), encoding="utf-8")
    return read_editable_config(path)
