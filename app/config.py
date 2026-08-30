"""Load .env credentials and config.yaml into typed objects.

只有这两个文件是配置源；敏感项只进 .env，业务配置进 config.yaml。
源群统一模型：所有 source_chats 一视同仁，各带 default_tags，可选指定
目标频道（缺省走全局 target_channel），支持多对多归档。
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
    target_channel_id: int | None = None


@dataclass(frozen=True)
class Config:
    api_id: int
    api_hash: str
    bot_token: str | None
    source_chats: list[SourceChat]
    target_channel_id: int
    forward_interval: float
    retry_count: int
    show_link: bool
    preserve_original: bool
    rating_enabled: bool
    admins: frozenset[int]
    url_template: str | None
    database_path: str
    config_path: str
    web_enabled: bool
    web_host: str
    web_port: int
    web_token: str

    def target_for(self, source_chat_id: int) -> int:
        """该源群的目标频道：源群指定优先，否则用全局 target_channel。"""
        for src in self.source_chats:
            if src.chat_id == source_chat_id and src.target_channel_id is not None:
                return src.target_channel_id
        return self.target_channel_id

    def all_target_channel_ids(self) -> set[int]:
        return {self.target_for(c.chat_id) for c in self.source_chats}


def _env_names(names: list[str]) -> dict[str, str]:
    """Return requested env vars, failing loudly with a fix hint when absent."""
    missing = [n for n in names if not os.getenv(n)]
    if missing:
        raise ConfigError(
            f"Missing env vars: {', '.join(missing)}. "
            "Copy .env.example to .env and fill in the values."
        )
    return {n: os.getenv(n) for n in names}


def _env_bool(name: str, *, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


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
            target_channel_id=(
                int(c["target_channel_id"]) if c.get("target_channel_id") is not None else None
            ),
        )
        for c in tg.get("source_chats", [])
    ]
    # 兼容旧配置：relay_chat 并入普通源群（统一模型，不保留特殊通道）。
    legacy_relay = tg.get("relay_chat") or {}
    if legacy_relay.get("chat_id") is not None:
        relay_id = int(legacy_relay["chat_id"])
        if relay_id not in {c.chat_id for c in source_chats}:
            source_chats.append(
                SourceChat(
                    chat_id=relay_id,
                    name=legacy_relay.get("name", "中转群"),
                    default_tags=list(legacy_relay.get("default_tags", [])),
                )
            )
    if not source_chats:
        raise ConfigError("telegram.source_chats is empty: configure at least one source chat.")

    target_channel_id = tg.get("target_channel", {}).get("chat_id")
    if target_channel_id is None:
        raise ConfigError("telegram.target_channel.chat_id is required.")

    admins = frozenset(int(x) for x in raw.get("admins", []))
    if not admins:
        raise ConfigError(
            "admins is empty: configure at least one admin user id in config.yaml."
        )

    web_enabled = _env_bool("WEB_ENABLED", default=True)
    web_token = os.getenv("WEB_TOKEN") or ""
    if web_enabled and not web_token:
        raise ConfigError(
            "WEB_TOKEN is required when WEB_ENABLED is true. "
            "Copy .env.example to .env and fill in a token (e.g. `openssl rand -hex 32`)."
        )

    return Config(
        api_id=api_id,
        api_hash=env["TELEGRAM_API_HASH"],
        bot_token=os.getenv("TELEGRAM_BOT_TOKEN") or None,
        source_chats=source_chats,
        target_channel_id=int(target_channel_id),
        forward_interval=float(fw.get("interval", 3)),
        retry_count=int(fw.get("retry_count", 3)),
        show_link=bool(src.get("show_link", True)),
        preserve_original=bool(tags_cfg.get("preserve_original", True)),
        rating_enabled=bool(rating.get("enabled", True)),
        admins=admins,
        url_template=search.get("url_template"),
        database_path=raw.get("database", {}).get("path", "archive.sqlite"),
        config_path=str(config_path),
        web_enabled=web_enabled,
        web_host=os.getenv("WEB_HOST", "127.0.0.1"),
        web_port=int(os.getenv("WEB_PORT", "8000")),
        web_token=web_token,
    )
