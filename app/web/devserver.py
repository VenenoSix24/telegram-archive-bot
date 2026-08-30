"""仅启动 Web 后端用于开发预览（不连接 Telegram）。

auth+/api 端点齐全；编辑端点因无 client 返回 503。真实运行走 python -m app。
"""

import asyncio
import os

import uvicorn

from app.config import load_config
from app.web.app import create_app


async def main() -> None:
    config = load_config()
    app = create_app(config, client=None, conn=None, indexer=None)
    port = int(os.environ.get("PORT", config.web_port))
    server = uvicorn.Server(
        uvicorn.Config(app, host=config.web_host, port=port, log_level="warning")
    )
    await server.serve()


if __name__ == "__main__":
    os.environ.setdefault("WEB_ENABLED", "true")
    asyncio.run(main())
