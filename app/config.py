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
class TargetChannel:
    chat_id: int
    name: str = ""
    private: bool = True


@dataclass(frozen=True)
class SourceChat:
    chat_id: int
    name: str
    default_tags: list[str] = field(default_factory=list)
    target_channel_ids: list[int] = field(default_factory=list)
    target_channel_id: int | None = None
    private: bool = True


@dataclass(frozen=True)
class Config:
    api_id: int
    api_hash: str
    bot_token: str | None
    source_chats: list[SourceChat]
    target_channels: list[TargetChannel] = field(default_factory=list)
    target_channel_id: int = 0
    sync_target_edits: bool = False
    forward_interval: float = 3.0
    retry_count: int = 3
    show_link: bool = True
    preserve_original: bool = True
    rating_enabled: bool = True
    admins: frozenset[int] = field(default_factory=frozenset)
    url_template: str | None = None
    database_path: str = "archive.sqlite"
    config_path: str = "config.yaml"
    web_enabled: bool = True
    web_host: str = "127.0.0.1"
    web_port: int = 8000
    web_token: str = ""
    thumbnail_media: str = "first_video"
    thumbnail_source: str = "auto"

    def targets_for(self, source_chat_id: int) -> list[int]:
        for source in self.source_chats:
            if source.chat_id == source_chat_id and source.target_channel_ids:
                return source.target_channel_ids
        if self.target_channels:
            return [target.chat_id for target in self.target_channels]
        if self.target_channel_id:
            return [self.target_channel_id]
        raise ConfigError(f"no target channel configured for source chat {source_chat_id}")

    def target_for(self, source_chat_id: int) -> int:
        return self.targets_for(source_chat_id)[0]

    def all_target_channel_ids(self) -> set[int]:
        ids = {target.chat_id for target in self.target_channels}
        ids.update(
            target_id
            for source in self.source_chats
            for target_id in source.target_channel_ids
        )
        if not ids and self.target_channel_id:
            ids.add(self.target_channel_id)
        return ids


def _chat_id(value, private: bool) -> int:
    number = int(value)
    if not private or number < 0:
        return number
    return -int(f"100{number}") if number < 10**12 else number


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
    thumbs = raw.get("thumbnails", {})
    sync_target_edits = bool(raw.get("sync_target_edits", False))

    source_chats = [
        SourceChat(
            chat_id=_chat_id(c["chat_id"], bool(c.get("private", True))),
            name=c.get("name", ""),
            default_tags=list(c.get("default_tags", [])),
            private=bool(c.get("private", True)),
            target_channel_ids=[
                _chat_id(x, bool(c.get("private", True)))
                for x in c.get("target_channel_ids", [])
            ] or (
                [_chat_id(c["target_channel_id"], bool(c.get("private", True)))]
                if c.get("target_channel_id") is not None
                else []
            ),
            target_channel_id=(
                int(c["target_channel_id"])
                if c.get("target_channel_id") is not None
                else None
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
                    target_channel_ids=[],
                    private=False,
                )
            )
    if not source_chats:
        raise ConfigError("telegram.source_chats is empty: configure at least one source chat.")

    target_channels = [
        TargetChannel(
            chat_id=_chat_id(c["chat_id"], bool(c.get("private", True))),
            name=c.get("name", ""),
            private=bool(c.get("private", True)),
        )
        for c in tg.get("target_channels", [])
    ]
    legacy_target = tg.get("target_channel") or {}
    if legacy_target.get("chat_id") is not None and not target_channels:
        target_channels.append(
            TargetChannel(
                chat_id=_chat_id(
                    legacy_target["chat_id"], bool(legacy_target.get("private", False))
                ),
                name=legacy_target.get("name", ""),
                private=bool(legacy_target.get("private", False)),
            )
        )
    if not target_channels:
        raise ConfigError(
            "telegram.target_channels is empty: configure at least one target channel."
        )

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
        target_channels=target_channels,
        target_channel_id=target_channels[0].chat_id,
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
        thumbnail_media=thumbs.get("media", "first_video"),
        thumbnail_source=thumbs.get("source", "auto"),
        sync_target_edits=sync_target_edits,
    )
