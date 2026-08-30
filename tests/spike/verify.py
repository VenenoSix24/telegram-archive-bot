"""技术验证 spike：三个高风险点的真实验证（文档第 52 节指定的阶段前置验证）。

用法（先 login via python -m app.auth）：
    python -m tests.spike.verify copy <chat_id> <message_id>
        把指定群的消息用 send_file(file=media) 复制到目标频道，验证"无下载复制 + 自定义 caption"。
        注意 product 逻辑用 -100 前缀 id 或裸内部 id 均可。
    python -m tests.spike.verify listen
        监听 source_chats 与 relay_chat，打印每条新消息的
        text / media_type / grouped_id / forward / reply 结构，
        用于判断转发评论关联与 Album 识别是否成立。

结论写入 docs/decisions/0002-技术验证.md（本地，不进公开仓库）。
"""

from __future__ import annotations

import asyncio
import sys

from telethon import events

from app.config import load_config
from app.telegram.client import build_client


def _print_event(m) -> None:
    media_type = type(m.media).__name__ if m.media else None
    forward_from = None
    if m.forward:
        fwd = m.forward
        peer = fwd.from_id
        forward_from = (
            f"user={peer.user_id}" if peer and peer.user_id else
            f"channel={peer.channel_id}" if peer and peer.channel_id else
            str(peer)
        )
    print(
        f"| chat={m.chat_id} msg={m.id} text={(m.message or '')[:60]!r} "
        f"media={media_type} grouped={m.grouped_id} "
        f"fwd_from={forward_from} reply_to={m.reply_to_msg_id}"
    )


async def _run() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 0

    config = load_config()
    client = build_client(config)
    await client.connect()
    if not await client.is_user_authorized():
        print("尚未登录：请先运行 python -m app.auth")
        await client.disconnect()
        return 3

    cmd = sys.argv[1]

    if cmd == "copy":
        if len(sys.argv) < 3:
            print("用法：python -m tests.spike.verify copy <chat_id> [message_id]")
            print("      不传 message_id 时自动取该群最新一条带媒体的消息。")
            return 2
        chat_id = int(sys.argv[2])
        message_id = int(sys.argv[3]) if len(sys.argv) > 3 else None
        src = await client.get_entity(chat_id)

        if message_id is None:
            msg = None
            async for m in client.iter_messages(src, limit=15):
                if m.media:
                    msg = m
                    break
            if msg is None:
                print(f"chat {chat_id} 最近 {15} 条里没有带媒体的消息")
                return 2
        else:
            msg = await client.get_messages(src, ids=message_id)
            if msg is None:
                print(f"取不到消息 {message_id}（chat {chat_id}）")
                return 2

        if not msg.media:
            print("该消息没有媒体；请选带图片/视频/文件的消息")
            return 2
        target = await client.get_entity(config.target_channel_id)
        caption = f"SPIKE 复制验证 #{msg.id}（来源 {chat_id}）"
        sent = await client.send_file(target, file=msg.media, caption=caption)
        print(f"OK：send_file 成功 → 目标频道消息 id={sent.id}")
        print(f"    自定义 caption 生效（{len(caption)} 字符）")
        print("    是否下载到服务器：调用无 download/upload，媒体以引用发送")
        return 0

    if cmd == "listen":
        ids = {c.chat_id for c in config.source_chats}
        if config.relay_chat_id:
            ids.add(config.relay_chat_id)
        print("正在监听 " + ", ".join(str(i) for i in sorted(ids)))
        print("请在 Telegram 客户端依次做三件事：")
        print("  1. 往来源群发一条带媒体的消息（图/视频/文件 + 文字）")
        print("  2. 往来源群发一组相册（2~3 张图一次发送）")
        print("  3. 在中转群对一条消息用「转发并在发送时加评论 /tag 游戏」")
        print("观察下方每行的 grouped=/fwd_from=/reply_to= 字段。Ctrl+C 结束。")

        @client.on(events.NewMessage(chats=list(ids)))
        async def handler(event):
            _print_event(event.message)

        try:
            await client.run_until_disconnected()
        finally:
            await client.disconnect()
        return 0

    print(__doc__)
    return 2


async def main() -> None:
    raise SystemExit(await _run())


if __name__ == "__main__":
    asyncio.run(main())
