"""Load .env credentials and config.yaml into typed objects.

只有这两个文件是配置源；敏感项只进 .env，业务配置进 config.yaml。
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from dotenv import load_dotenv


class ConfigError(Exception):
    pass


@dataclass(frozen=True)
class SourceChat:
    chat_id: int
    name: str
    default_tags: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class Config:
    api_id: int
    api_hash: str
    bot_token: str | None
    source_chats: list[SourceChat]
    target_channel_id: int
    relay_chat_id: int | None
    forward_interval: float
    retry_count: int
    show_link: bool
    preserve_original: bool
    rating_enabled: bool
    admins: frozenset[int]
    url_template: str | None


def _env_names(names: list[str]) -> dict[str, str]:
    """Return requested env vars, failing loudly with a fix hint when absent."""
    missing = [n for n in names if not os.getenv(n)]
    if missing:
        raise ConfigError(
            f"Missing env vars: {', '.join(missing)}. "
            "Copy .env.example to .env and fill in the values."
        )
    return {n: os.getenv(n) for n in names}


def load_config(config_path: str | Path = "config.yaml") -> Config:
    load_dotenv()
    env = _env_names(["TELEGRAM_API_ID", "TELEGRAM_API_HASH"])
    try:
        api_id = int(env["TELEGRAM_API_ID"])
    except ValueError:
        raise ConfigError(
            "TELEGRAM_API_ID must be an integer, got: " + env["TELEGRAM_API_ID"]
        ) from None

    raw = yaml.safe_load(Path(config_path).read_text(encoding="utf-8"))
    tg = raw.get("telegram", {})
    fw = raw.get("forward", {})
    src = raw.get("source", {})
    tags_cfg = raw.get("tags", {})
    rating = raw.get("rating", {})
    search = raw.get("search", {})

    source_chats = [
        SourceChat(
            chat_id=int(c["chat_id"]),
            name=c.get("name", ""),
            default_tags=list(c.get("default_tags", [])),
        )
        for c in tg.get("source_chats", [])
    ]
    if not source_chats:
        raise ConfigError("telegram.source_chats is empty: configure at least one source chat.")

    target_channel_id = tg.get("target_channel", {}).get("chat_id")
    if target_channel_id is None:
        raise ConfigError("telegram.target_channel.chat_id is required.")

    relay_chat = tg.get("relay_chat") or {}
    admins = frozenset(int(x) for x in raw.get("admins", []))
    if not admins:
        raise ConfigError(
            "admins is empty: configure at least one admin user id in config.yaml."
        )

    return Config(
        api_id=api_id,
        api_hash=env["TELEGRAM_API_HASH"],
        bot_token=os.getenv("TELEGRAM_BOT_TOKEN") or None,
        source_chats=source_chats,
        target_channel_id=int(target_channel_id),
        relay_chat_id=int(relay_chat["chat_id"]) if relay_chat.get("chat_id") is not None else None,
        forward_interval=float(fw.get("interval", 3)),
        retry_count=int(fw.get("retry_count", 3)),
        show_link=bool(src.get("show_link", True)),
        preserve_original=bool(tags_cfg.get("preserve_original", True)),
        rating_enabled=bool(rating.get("enabled", True)),
        admins=admins,
        url_template=search.get("url_template"),
    )
