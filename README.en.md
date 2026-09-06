# Telegram Archive Bot

![Telegram Archive Bot](docs/screenshots/cover.png)

[![CI](https://img.shields.io/github/actions/workflow/status/VenenoSix24/telegram-archive-bot/ci.yml?label=CI)](https://github.com/VenenoSix24/telegram-archive-bot/actions/workflows/ci.yml)
![Version](https://img.shields.io/badge/version-0.6.0-blue)
![Python](https://img.shields.io/badge/python-3.11%2B-informational)
![Web](https://img.shields.io/badge/web-Vue%203%20%C2%B7%20Tailwind-42b883)
![License](https://img.shields.io/badge/license-MIT-green)

> English ｜ [简体中文](README.md)

A Telegram message archiving tool.

It watches selected Telegram groups and channels, copies new messages to your target group or channel, and stores the message mapping, tags, ratings and source info in SQLite. A web admin panel lets you search, filter and edit the archive — edits are synced back to Telegram.

Media files are never downloaded to the server: archived messages use Telegram's copy of the original message. The server only keeps the database and small thumbnails for web preview.

## Features

- Auto archiving: watches source chats and copies messages through a queue, with rate limiting, retries and recovery after restarts
- Many-to-many routing: multiple sources, multiple targets; each source can have default tags and its own target
- Tags: stored as structured data, with a pinned tag index maintained per target channel
- Ratings: 0–5 stars, shown in the message header and usable as a filter
- Full-text search: backed by SQLite FTS5, handles Chinese and English keywords and multi-term queries
- Web admin panel: browse, search, filter, edit, back up and export
- Two-way sync: edits and deletions made in Telegram are reflected in the database and web panel
- Message template: reorder rating, tags, body and source sections via `message_template`
- Scheduled backups: automatic SQLite backups on an interval, optionally uploaded to a Telegram chat
- Data export: export everything, or your current filtered view, as CSV / JSON

## Screenshots

Overview dashboard (stats, 30-day trend, queue and recent activity):

![Overview](docs/screenshots/desktop-overview.png)

Archive browsing with the minimal theme, and the album view of the collection theme:

<table>
  <tr>
    <td width="50%" align="center"><img src="docs/screenshots/desktop-archive.png" alt="Archive browsing (minimal theme)" /></td>
    <td width="50%" align="center"><img src="docs/screenshots/desktop-collection.png" alt="Album view (collection theme)" /></td>
  </tr>
</table>

Mobile (responsive layout):

<table>
  <tr>
    <td width="50%" align="center"><img src="docs/screenshots/phone-overview.jpg" alt="Mobile overview" width="300" /></td>
    <td width="50%" align="center"><img src="docs/screenshots/phone-archive.jpg" alt="Mobile archive" width="300" /></td>
  </tr>
</table>

## How it works

```text
Source A ──┐
Source B ──┼─→ watch → SQLite → queue → copy → target channel(s)
Relay ─────┘             │
                    └──── Web (FastAPI + Vue 3)
                           │
                           └─ search / edit → write DB → update Telegram
```

The project keeps Telegram and SQLite separate on purpose:

1. Telegram stores the media and displays the archived messages.
2. SQLite stores the message mapping, tags, ratings, source info and processing state.
3. The program does the watching, queueing, copying and the sync between both ends.

## Quick Start

### Requirements

- Python 3.11+
- A dedicated Telegram account — a burner account is recommended
- A Telegram API ID / API Hash from [my.telegram.org](https://my.telegram.org/)

### Install

Get the code first (git clone, or download a source archive from the Releases page):

```bash
git clone https://github.com/VenenoSix24/telegram-archive-bot.git
cd telegram-archive-bot
```

Then install the dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Configure

Copy `.env.example` to `.env` (credentials) and `config.example.yaml` to `config.yaml` (everything else):

```bash
cp .env.example .env
cp config.example.yaml config.yaml
```

Edit `.env`:

```dotenv
TELEGRAM_API_ID=...
TELEGRAM_API_HASH=...
WEB_TOKEN=...
```

For `WEB_TOKEN`, use a random string, for example:

```bash
openssl rand -hex 32
```

`config.yaml` can be edited by hand or through the Settings page of the web panel (a restart is required after saving). The fields you need to fill in:

- `source_chats`
- `target_channels`
- `admins`

### Login

Authenticate on first run:

```bash
python -m app.auth
```

Follow the prompts for your phone number, the login code and your two-step verification password. This creates `telegram_archive.session`.

### Start

```bash
python -m app
```

The web panel is at:

```text
http://127.0.0.1:8000
```

Log in with `WEB_TOKEN`.

If you don't know a chat's `chat_id`, add the program's account to the group or channel and send:

```text
/id
```

It will reply with the chat ID and your user ID.

## Docker

If you'd rather not set up a Python environment, use Docker Compose.

Copy `.env.example` to `.env` and `config.example.yaml` to `config.yaml`, fill them in, then:

```bash
docker compose up -d --build
```

The frontend is built during the image build, so no Node.js is needed on the server.

## Configuration

Credentials go in `.env`, everything else goes in `config.yaml`. Besides editing the files by hand, most settings can also be changed on the Settings page of the web panel (restart after saving).

See [config.example.yaml](https://github.com/VenenoSix24/telegram-archive-bot/blob/main/config.example.yaml) for the full list of fields.

The `ARCHIVE_CONFIG` environment variable can be used to point to a different config file.

### `.env`

| Variable | Required | Description |
| --- | --- | --- |
| `TELEGRAM_API_ID` / `TELEGRAM_API_HASH` | Yes | Telegram API credentials |
| `TELEGRAM_BOT_TOKEN` | No | Reserved; the current version logs in with a personal account |
| `WEB_ENABLED` | No | Enable the web panel, default `true` |
| `WEB_HOST` | No | Web listen address, default `127.0.0.1` |
| `WEB_PORT` | No | Web port, default `8000` |
| `WEB_TOKEN` | Required when `WEB_ENABLED=true` | Web login token |
| `LOG_LEVEL` | No | Log level: `DEBUG` / `INFO` / `WARNING`, default `INFO` |

### `config.yaml`

| Field | Description |
| --- | --- |
| `telegram.source_chats[]` | Source chats: `chat_id`, `name`, `default_tags`; optional `target_channel_ids` to pick a target, `private` controls the automatic `-100` prefix |
| `telegram.target_channels[]` | Target channels: `chat_id`, `name` |
| `forward.interval` | Seconds between sends, default `3` |
| `forward.retry_count` | Max retries before a message is marked failed, default `3` |
| `source.show_link` | Show the source link in archived messages, default `true` |
| `tags.preserve_original` | Keep hashtags from the original message, default `true` |
| `rating.enabled` | Enable ratings, default `true` |
| `thumbnails.media` | Which album item to thumbnail: `first_video` / `first`, default `first_video` |
| `thumbnails.source` | Thumbnail source: `auto` / `archive` / `source`, default `auto` |
| `message_template` | Section order, default `[rating, tags, body, source]`; `body` must be kept |
| `backup.enabled` | Scheduled backups, default `true` |
| `backup.interval_days` | Backup interval: `1` / `3` / `7` / `30`, default `7` |
| `backup.retain` | How many backups to keep locally, default `7` |
| `backup.upload_chat_id` | Optional; upload each backup to this Telegram chat |
| `admins` | Admin user IDs |
| `database.path` | SQLite path, default `archive.sqlite` |

## Message Format

The default message layout:

```text
推荐指数：⭐⭐⭐⭐⭐

#存档 #Archive #Nice

收藏的消息再也不乱啦！

来自：
https://t.me/xxx/123
```

Tags are space-separated and stored as a structured list.

A rating of `0` clears the rating and is not rendered.

## Commands

Admins (the `admins` list in `config.yaml`) can use these commands in any connected chat.

### Reply commands

Reply to an archived message and send:

| Command | Description |
| --- | --- |
| `/tag <tags…>` | Add tags to the replied-to message |
| `/rating <0-5>` | Set the rating, `0` clears it |

### General commands

Sent on their own:

| Command | Description |
| --- | --- |
| `/status` | Watched chats, targets, queue and worker status |
| `/queue` | Queue overview: pending, failed, ETA |
| `/tags` | Tag statistics |
| `/pause` / `/resume` | Pause / resume the queue |
| `/rethumb [N]` | Re-fetch thumbnails for the last N messages, default `100` |
| `/id` | Show the current chat ID |
| `/start` / `/help` | Command list |

## Web Panel

The archiving pipeline and the web panel run in the same process:

- **Dashboard**: archive stats, 30-day trend, queue status and recent activity
- **Archive**: filter by keyword, tag, rating, media type and source; rating and tag edits sync back to Telegram
- **Tags**: tag usage
- **Settings**: config editor, database backup / restore / import / reset, recent failures, CSV / JSON export
- **Themes**: a minimal and a collection theme, with light, dark and system color modes

The panel only listens on `127.0.0.1:8000` by default.

For LAN access:

```dotenv
WEB_HOST=0.0.0.0
```

then open:

```text
http://<lan-ip>:8000
```

For a public deployment, put Nginx or Caddy in front and enable HTTPS.

### Health Check

An unauthenticated endpoint:

```text
GET /health
```

reports database status and the last background task failure, and can be used as a Docker `HEALTHCHECK` or for reverse-proxy probes.

### Web-only Dev Server

To work on the web panel without connecting to Telegram:

```bash
python -m app.web.devserver
```

Edit endpoints return `503` in this mode.

## Data & Backup

| Path | Description |
| --- | --- |
| `telegram_archive.session` | Telegram login state; back it up when migrating servers |
| `archive.sqlite` | SQLite database with all structured data |
| `logs/` | Logs |
| `thumbs/` | Thumbnail cache, rebuild with `/rethumb` |

The database schema is managed by the SQL migrations in `migrations/`, applied automatically at startup.

## Development

### Backend

Python 3.11+:

```bash
pip install -r requirements-dev.txt

ruff check app tests
pytest
```

### Frontend

The frontend lives in `web/`, built with pnpm + Node 22:

```bash
cd web

pnpm install --frozen-lockfile
pnpm dev
pnpm test
pnpm lint
pnpm build
```

The dev server runs on `:5173` and proxies `/api` to `127.0.0.1:8000`.

### CI

GitHub Actions runs:

- Backend: `ruff check` + `pytest`
- Frontend: `pnpm lint` + `pnpm test` + `pnpm build`
- Docker: builds the image to verify the Dockerfile

## Project Structure

```text
app/
├── processor/        # Telegram event handling
├── queue/            # Send queue: rate limiting, retries, recovery
├── renderer/         # Archived message rendering
├── tags/             # Tag engine and pinned index
├── telegram/         # Telethon client and message copying
├── media/            # Thumbnails and backfill
└── web/              # FastAPI, auth, config, backups and export

migrations/           # SQLite migrations
web/                  # Vue 3 + Tailwind frontend
tests/                # pytest tests
```

## FAQ

### Is this a Bot API bot?

No.

The project runs as a personal account (user-bot) via Telethon; `TELEGRAM_BOT_TOKEN` is a reserved field and currently unused.

Use a dedicated account and make it an admin of the target channels.

### Are media files downloaded to the server?

No.

Archived messages use Telegram's copy of the original message, so media stays in Telegram. The server only keeps thumbnails for web preview.

### If I edit tags or a rating in the web panel, does the Telegram message update?

Yes.

Saving writes to the database and re-renders the corresponding Telegram message and tag index.

The reverse also works: edits and deletions made in Telegram are picked up by the database and the web panel.

### I changed `config.yaml` but nothing happened?

Changes made through the web panel require a restart.

A `config.yaml.bak` is created automatically before each save.

Render settings like `message_template` only affect messages archived afterwards.

### The process died mid-queue. What now?

At startup the queue resets interrupted `processing` items back to `pending` and carries on.

### I forgot the web login token

Set a new `WEB_TOKEN` in `.env` and restart.

Browser sessions are invalidated by a restart, so you'll need to log in again.

## License

[MIT](LICENSE) © 2026 VenenoSix24
