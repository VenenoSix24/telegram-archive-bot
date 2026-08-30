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
# fill .env with API_ID/API_HASH
# fill config.yaml with source_chats/target_channel chat_ids and admins

python -m app.auth   # interactive first login: phone → code → 2FA, creates session
python -m app        # run
```

> Get chat ids: reply `/id` in any source chat or the target channel and the bot echoes current chat/sender id.

## Configuration

| File | Content |
|---|---|
| `.env` | API credentials, Web settings (`WEB_ENABLED` / `WEB_HOST` / `WEB_PORT` / `WEB_TOKEN`, not committed) |
| `config.yaml` | source chats (default tags, optional per-source target), target channel, rate limit, tag/rating toggles, search template, admins |

See [config.example.yaml](config.example.yaml) for all fields.

## Message format

Rendered by the Renderer with fixed order:

```
推荐指数：⭐⭐⭐⭐⭐
#游戏 #GTA5 #MOD

GTA5 NVE 教程


来自：
https://t.me/xxx/123
```

Tags are space-separated (never newline, never concatenated); the database stores a structured list, not a joined string.

## Admin commands

Admins (`config.yaml` `admins`) reply to an archived message in a source chat or the target channel:

| Command | Effect |
|---|---|
| `/tag GTA5 MOD` | Add tags to the replied message |
| `/rating 5` | Set rating 0~5 |
| `/status` | System status |
| `/queue` | Queue stats |
| `/pause` / `/resume` | Pause / resume queue |
| `/id` | Print chat/sender id |

## Deploy

Docker (requires Docker Desktop installed locally):

```bash
# 1. First login: interactive phone → code → 2FA, creates session
docker compose run --rm app python -m app.auth
# 2. Start
docker compose up -d
```

Session, database and logs persist via compose volumes (`telegram_archive.session` / `archive.sqlite` / `logs/`); the queue recovers on restart.

## Web UI (V2)

One process runs both the Telegram archiving pipeline and a FastAPI Web UI (Vue 3 SPA).

```text
127.0.0.1:8000  →  Web UI (localhost by default)
```

- Login with `WEB_TOKEN` (a strong random string in `.env`); the browser keeps the session, re-login after restart
- Browse archived messages, thumbnails, search, filter by Tag / rating / media type
- Open a message to **edit rating and add / remove Tags** — writes DB → re-renders → updates the message
  and pinned Tag index in the target channel. Telegram and Web stay in sync (DB is the single source of truth)
- Thumbnails are small local files for browsing only; full media always opens back in Telegram (no media vault)

### Local run

`.env` already has `WEB_ENABLED=true` / `WEB_HOST=127.0.0.1` / `WEB_PORT=8000` / `WEB_TOKEN`. Just run:

```bash
python -m app        # then open http://127.0.0.1:8000
```

### Docker deploy

Compose maps `WEB_PORT`; inside the container set `WEB_HOST=0.0.0.0` to expose it:

```bash
# .env
WEB_HOST=0.0.0.0
```

```bash
docker compose up -d   # frontend is built into the image (multi-stage); no Node needed locally
```

> On a server, put Caddy / Nginx in front with HTTPS.

## Backup

- `telegram_archive.session`: Telegram login state; back it up manually for server migration (not committed).
- Database file, `logs/` and `thumbs/` (thumbnail cache) are persisted via volumes.

## Development

```bash
pip install -r requirements-dev.txt
ruff check app tests
pytest
```

## License

MIT (draft).