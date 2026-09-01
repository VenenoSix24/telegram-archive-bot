"""把 uvicorn server 并入主事件循环的辅助入口。

Telethon 的 run_until_disconnected 和 uvicorn 在同一 asyncio loop 跑：
uvicorn serve() 是 async 方法，直接 create_task 即可，无需独立进程/端口转发。
"""

from __future__ import annotations

import logging

import uvicorn

from app.config import Config
from app.web.app import create_app

logger = logging.getLogger(__name__)


def start_server_task(
    config: Config,
    *,
    client=None,
    conn=None,
    indexer=None,
    chat_names: dict[int, str] | None = None,
    queue=None,
) -> uvicorn.Server:
    """Build app + uvicorn server; caller runs serve() as an asyncio task."""
    app = create_app(
        config,
        client=client,
        conn=conn,
        indexer=indexer,
        chat_names=chat_names,
        queue=queue,
    )
    server = uvicorn.Server(
        uvicorn.Config(
            app,
            host=config.web_host,
            port=config.web_port,
            log_config=None,  # 不覆盖 app 的日志配置
            access_log=False,
        )
    )
    # Web 地址由 main.py 的启动横幅集中展示，这里降为 debug 避免 URL 重复刷屏
    logger.debug("web UI on http://%s:%d", config.web_host, config.web_port)
    return server
