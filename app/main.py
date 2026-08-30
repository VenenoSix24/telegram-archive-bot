"""Entry point. Phase 0: config 校验 + logging；Telegram 连接在 Phase 1 接入。"""

from __future__ import annotations

import logging

from app.config import ConfigError, load_config
from app.logging_setup import setup_logging

logger = logging.getLogger(__name__)


def main() -> None:
    setup_logging()
    try:
        config = load_config()
    except ConfigError as exc:
        logger.error("%s", exc)
        raise SystemExit(2) from exc

    logger.info(
        "config loaded: %d source chats, target=%s%s, interval=%ss, retry=%d, admins=%s",
        len(config.source_chats),
        config.target_channel_id,
        f", relay={config.relay_chat_id}" if config.relay_chat_id else "",
        config.forward_interval,
        config.retry_count,
        sorted(config.admins),
    )


if __name__ == "__main__":
    main()
