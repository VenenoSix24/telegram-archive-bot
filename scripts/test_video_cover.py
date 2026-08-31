"""实验：验证无引用复制时能否保留 Telegram video_cover。"""

from __future__ import annotations

import argparse
import asyncio

from telethon import utils

from app.config import load_config
from app.telegram.client import build_client


def describe(label, message) -> None:
    media = getattr(message, "media", None)
    document = getattr(media, "document", None)
    print(f"\n=== {label} ===")
    print("message_id:", getattr(message, "id", None))
    print("grouped_id:", getattr(message, "grouped_id", None))
    print("media_type:", type(media).__name__ if media else None)
    print("document_id:", getattr(document, "id", None))
    print("document_thumbs:", len(getattr(document, "thumbs", None) or []))
    print("document_video_thumbs:", len(getattr(document, "video_thumbs", None) or []))
    print("video_cover:", bool(getattr(media, "video_cover", None)))
    print("alt_documents:", len(getattr(media, "alt_documents", None) or []))
    print("document_dc_id:", getattr(document, "dc_id", None))


async def run(source_chat: int, source_message: int, target_chat: int) -> None:
    config = load_config()
    client = build_client(config)
    await client.connect()
    try:
        source_entity = await client.get_entity(source_chat)
        target_entity = await client.get_entity(target_chat)
        source = await client.get_messages(source_entity, ids=source_message)
        if source is None or source.media is None:
            raise RuntimeError("source message has no media")
        describe("SOURCE", source)

        media = source.media
        document = getattr(media, "document", None)
        cover = getattr(media, "video_cover", None)
        if document is None or cover is None:
            raise RuntimeError("source message has no document/video_cover")

        input_media = utils.get_input_media(document)
        input_media.video_cover = utils.get_input_photo(cover)
        sent = await client.send_file(
            target_entity,
            file=input_media,
            caption="[video_cover experiment]",
            parse_mode="html",
        )
        target = sent[0] if isinstance(sent, list) else sent
        print("\nsent_message_id:", target.id)

        fetched = await client.get_messages(target_entity, ids=target.id)
        if fetched is not None:
            describe("TARGET", fetched)
    finally:
        await client.disconnect()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source_chat", type=int)
    parser.add_argument("source_message", type=int)
    parser.add_argument("target_chat", type=int)
    args = parser.parse_args()
    asyncio.run(run(args.source_chat, args.source_message, args.target_chat))


if __name__ == "__main__":
    main()
