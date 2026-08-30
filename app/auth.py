"""交互式首次登录：python -m app.auth

按提示输入手机号 → 验证码 → （如开启）两步验证密码，生成 telegram_archive.session。
登录态保存在本地，不会进入 Git；服务器迁移时手动备份该文件。
"""

from __future__ import annotations

import asyncio

from app.config import ConfigError, load_config
from app.logging_setup import setup_logging
from app.telegram.client import build_client


def _ask(prompt: str) -> str:
    return input(prompt).strip()


async def _run() -> int:
    setup_logging()
    try:
        config = load_config()
    except ConfigError as exc:
        print(f"配置错误：{exc}")
        return 2

    client = build_client(config)
    await client.connect()

    if await client.is_user_authorized():
        me = await client.get_me()
        print(f"已登录：{me.first_name} (id={me.id})，session 已存在。")
    else:
        await client.start(
            phone=lambda: _ask("手机号（含国家代码，如 +8613800138000）: "),
            code_callback=lambda: _ask("Telegram 发来的验证码: "),
            password=lambda: _ask("两步验证密码（没有直接回车）: "),
        )
        me = await client.get_me()
        print(f"登录成功：{me.first_name} (id={me.id})，session 已保存。")

    await client.disconnect()
    return 0


def main() -> None:
    raise SystemExit(asyncio.run(_run()))


if __name__ == "__main__":
    main()
