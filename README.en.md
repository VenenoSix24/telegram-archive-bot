# Telegram Archive Bot

> Personal information archiving and knowledge management on Telegram + Telethon
> [中文](README.md)

Archive content from multiple categorized group chats into a unified channel, managed with tags, ratings, source indexes and a database.

## Core philosophy

- **Telegram stores media**: the target channel (broadcast channel + linked discussion group) is the reading surface.
- **Database stores structure**: message mapping, tags, ratings, sources, status.
- **The program connects both**: collect → Tag Engine → Renderer → Queue → target channel.

Media is reused by reference, never downloaded and re-uploaded.

## Quick start

Prereq: Python 3.11+, a dedicated Telegram account, API ID / Hash from [my.telegram.org](https://my.telegram.org).

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
cp config.example.yaml config.yaml
# fill .env with API_ID/API_HASH/ADMIN_IDS
# fill config.yaml with source_chats/target_channel/relay_chat chat_ids

python -m app.auth   # interactive first login: phone → code → 2FA, creates session
python -m app        # run
```

> Get chat ids: reply `/id` in the relay chat and the bot echoes current chat/sender id.

## Configuration

| File | Content |
|---|---|
| `.env` | API credentials, admin ids (not committed) |
| `config.yaml` | source chats, target channel, relay chat, rate limit, tag/rating toggles, search template |

See [config.example.yaml](config.example.yaml) for all fields.

## Message format

Rendered by the Renderer with fixed order:

```
⭐⭐⭐⭐⭐
#游戏 #GTA5 #MOD

GTA5 NVE 教程


来自：
https://t.me/xxx/123
```

Tags are space-separated (never newline, never concatenated); the database stores a structured list, not a joined string.

## Admin commands

Admins (`ADMIN_IDS`) reply to an archived message in the linked discussion group:

| Command | Effect |
|---|---|
| `/tag GTA5 MOD` | Add tags to the replied message |
| `/rating 5` | Set rating 0~5 |
| `/status` | System status |
| `/queue` | Queue stats |
| `/pause` / `/resume` | Pause / resume queue |
| `/id` | Print chat/sender id |

## Deploy

Docker (to be verified in Phase 12):

```bash
docker compose up -d
```

## Backup

- `telegram_archive.session`: Telegram login state; back it up manually for server migration (not committed).
- Database file and `logs/` are persisted via volumes.

## Development

```bash
pip install -r requirements-dev.txt
ruff check app tests
pytest
```

## License

MIT (draft).