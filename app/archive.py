"""手动归档单条消息：python -m app.archive <chat_id> <message_id>

把指定消息走完整链路：适配 → 落库（去重）→ 复制到目标频道 → 回填 DB。
用于人工触发归档与验证 Phase 3 闭环；自动监听在 Phase 2 接入同一管道。
"""

from __future__ import annotations

import asyncio
import sys

from app.config import ConfigError, load_config
from app.database.migrate import apply_migrations, open_db
from app.processor.adapter import build_incoming, resolve_source_url
from app.processor.recorder import record_message
from app.telegram.client import build_client
from app.telegram.copier import archive_message_by_db_id, collect_album


async def _run() -> int:
    if len(sys.argv) < 3:
        print(__doc__)
        return 0

    try:
        config = load_config()
    except ConfigError as exc:
        print(f"配置错误：{exc}")
        return 2

    conn = open_db(config.database_path)
    apply_migrations(conn)

    client = build_client(config)
    await client.connect()
    if not await client.is_user_authorized():
        print("尚未登录：请先运行 python -m app.auth")
        await client.disconnect()
        conn.close()
        return 3

    chat_id = int(sys.argv[1])
    message_id = int(sys.argv[2])
    chat = await client.get_entity(chat_id)
    msg = await client.get_messages(chat, ids=message_id)
    if msg is None:
        print(f"取不到消息 {message_id}（chat {chat_id}）")
        await client.disconnect()
        conn.close()
        return 2

    # 相册锚定组首条，保证文字/tag 挂锚、同组只归档一次（避免重复）。
    anchor = (await collect_album(client, chat, msg))[0]

    chat_cfg = next((c for c in config.source_chats if c.chat_id == chat_id), None)
    source_tags = chat_cfg.default_tags if chat_cfg else []
    source_url = await resolve_source_url(
        client, anchor, chat, show_link=config.show_link
    )
    incoming = build_incoming(anchor, chat_id, source_url)

    mid = record_message(
        conn,
        incoming,
        source_tags=source_tags,
        preserve_original=config.preserve_original,
        template_layout=config.message_template,
    )
    if mid is None:
        print("该源消息已归档过，跳过。")
    else:
        target_id = await archive_message_by_db_id(client, config, conn, mid)
        print(f"归档完成：来源 {chat_id}/{message_id} → 目标消息 {target_id}")

    await client.disconnect()
    conn.close()
    return 0


async def main() -> None:
    raise SystemExit(await _run())


if __name__ == "__main__":
    asyncio.run(main())
