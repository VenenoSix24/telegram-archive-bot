"""列出当前账号参与的对话，用于填 config.yaml 的 chat_id。

用法：python -m app.dialogs
登录后运行，输出每行：chat_id  名称  类型（Chat / Channel / User）。
"""

from __future__ import annotations

import asyncio

from app.config import ConfigError, load_config
from app.telegram.client import build_client


async def _run() -> int:
    try:
        config = load_config()
    except ConfigError as exc:
        print(f"配置错误：{exc}")
        return 2

    client = build_client(config)
    await client.connect()
    if not await client.is_user_authorized():
        print("尚未登录：请先运行 python -m app.auth")
        await client.disconnect()
        return 3

    async for dialog in client.iter_dialogs():
        entity_type = type(dialog.entity).__name__
        print(f"{dialog.id}\t{dialog.name}\t{entity_type}")

    await client.disconnect()
    return 0


def main() -> None:
    raise SystemExit(asyncio.run(_run()))


if __name__ == "__main__":
    main()
