# Telegram Archive Bot

<p align="left">
  <!-- TODO(badge): add real CI / coverage badge links once the repo is public -->
  <img alt="version" src="https://img.shields.io/badge/version-0.5.0-blue" />
  <img alt="python" src="https://img.shields.io/badge/python-3.11%2B-informational" />
  <img alt="license" src="https://img.shields.io/badge/license-MIT-green" />
</p>

> English ｜ [中文](README.md)

**Turn the firehose of your Telegram group chats into a searchable, editable personal knowledge base.**

The bot watches the source groups you configure and copies every new message — by Telegram reference, never re-uploading media — into your target channel(s). Tags, ratings, sources and message state live in SQLite and stay in sync between Telegram and a built-in web dashboard.

<!-- Screenshot placeholder: web dashboard, message list (light theme) -->
<!-- <img src="docs/screenshots/web-messages-light.png" width="720" /> -->

## Why this exists

Most "save it for later" workflows on Telegram die in an unsorted channel. This project treats Telegram as the **storage and reading surface** and a database as the **source of truth**:

- **Telegram stores media.** The target channel (broadcast channel + linked discussion group) is the final reading experience.
- **SQLite stores structure.** Message mappings, tags, ratings, sources and status — one database, synced both ways.
- **The program connects the two.** Collect → queue → copy; edits can start from either side and propagate automatically.

## Features

- **Automatic archiving** — incoming messages from source groups flow through a rate-limited queue into your target channel(s), with retries and automatic queue recovery after restarts.
- **Many-to-many routing** — multiple source groups, multiple target channels; each source can carry default tags and its own targets. A relay group is just another source: forward old messages into it and tag them with a reply.
- **Tag engine** — space-separated tags stored as structured lists (never a joined string), plus a **pinned tag index message** per target channel that auto-refreshes (debounced) as tags change.
- **Ratings** — 0–5 stars rendered into the message header and filterable in the web UI.
- **Custom message layout** — a `message_template` controls the order of rating / tags / body / source blocks; remove a block to hide it.
- **Web dashboard** — a Vue 3 + Tailwind SPA served by the same process: browse, search, filter by keyword / tag / rating / media type, and edit ratings and tags in place. Saving re-renders the message and updates it — and the pinned index — back in Telegram.
- **Edit & delete mirroring** — edit or delete an archived message in Telegram and the database (and web UI) follows along.
- **Thumbnails without a media vault** — small preview images are cached locally for browsing only; full media always opens back in Telegram.
- **Ops built in** — config editor (auto-backups `config.yaml.bak` on save), config & database backup / restore / import, and database reset, all from the web UI.

## Architecture

```text
source group A ──┐
source group B ──┼─→ listener → SQLite (tags/rating/source/status) → queue → copy → target channel(s)
relay group   ──┘                                                        │
                    Web dashboard (FastAPI + Vue 3 SPA) ←────────────────┘
                    browse / search / edit → write DB → re-render → update Telegram messages & pinned index
```

## Quick start

Prerequisites: Python 3.11+, a dedicated Telegram account, and an API ID / API Hash from [my.telegram.org](https://my.telegram.org).

```bash
# 1. Install
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 2. Configure
cp .env.example .env
cp config.example.yaml config.yaml
# .env: fill in TELEGRAM_API_ID / TELEGRAM_API_HASH and set WEB_TOKEN to a strong
#       random string (openssl rand -hex 32)
# config.yaml: fill in source_chats / target_channels chat_ids and admins (your user id)

# 3. First login (interactive: phone → code → 2FA password), creates telegram_archive.session
python -m app.auth

# 4. Run
python -m app
```

Then open `http://127.0.0.1:8000` and log in with `WEB_TOKEN`.

> **Finding chat ids:** add the account to any source group or target channel and send it `/id` — it replies with the current chat id and your user id, ready to paste into `config.yaml`.

<!-- Screenshot placeholder: startup banner / first-login flow -->

## Configuration

Secrets live in `.env` (not committed); everything else lives in `config.yaml`. Set the `ARCHIVE_CONFIG` environment variable to use a different config file location.

**`.env`**

| Variable | Required | Description |
|---|---|---|
| `TELEGRAM_API_ID` / `TELEGRAM_API_HASH` | yes | From [my.telegram.org](https://my.telegram.org) |
| `TELEGRAM_BOT_TOKEN` | no | Reserved for future use; the current architecture runs as a user account (user-bot), not the Bot API |
| `WEB_ENABLED` | no | Defaults to `true` |
| `WEB_HOST` | no | Defaults to `127.0.0.1`; set to `0.0.0.0` for LAN access |
| `WEB_PORT` | no | Defaults to `8000` |
| `WEB_TOKEN` | required when `WEB_ENABLED=true` | Dashboard login token, e.g. `openssl rand -hex 32` |
| `LOG_LEVEL` | no | Terminal log level `DEBUG / INFO / WARNING`, default `INFO`; details always go to `logs/app.log` |

**`config.yaml`**

| Key | Description |
|---|---|
| `telegram.source_chats[]` | Source groups: `chat_id`, `name`, `default_tags`; optional `target_channel_ids` to route to specific targets (defaults to all target channels); `private` controls auto `-100` prefixing |
| `telegram.target_channels[]` | Target channels: `chat_id`, `name` |
| `forward.interval` | Seconds between sends, default `3` |
| `forward.retry_count` | Max retries before a message is marked failed, default `3` |
| `source.show_link` | Show the "from" source link in archived messages, default `true` |
| `tags.preserve_original` | Keep hashtags from the original message, default `true` |
| `rating.enabled` | Enable ratings, default `true` |
| `thumbnails.media` | Which album item becomes the thumbnail: `first_video` (default) / `first` |
| `thumbnails.source` | Thumbnail source: `auto` (default, archive preferred, fall back to source) / `archive` / `source` |
| `message_template` | Block order, default `[rating, tags, body, source]`; `body` is mandatory; changes only affect messages archived afterwards |
| `backup.enabled` | Scheduled auto-backup switch, default `true` |
| `backup.interval_days` | Backup interval in days: `1` / `3` / `7` (default) / `30`; runs while the app is up, catches up on next start |
| `backup.retain` | How many newest local backups to keep, default `7` |
| `backup.upload_chat_id` | Optional Telegram chat ID to receive each backup file; upload failures never affect the local backup |
| `admins` | Admin user ids allowed to run commands |
| `database.path` | SQLite path, default `archive.sqlite` (relative paths resolve against the directory containing `config.yaml`) |

See [config.example.yaml](https://github.com/VenenoSix24/telegram-archive-bot/blob/main/config.example.yaml) for a full annotated example.

<!-- TODO(config): the old README mentioned a "search link template" config; it no longer exists in config.py / config.example.yaml — confirm it was removed before documenting anything similar -->

## Message format

The renderer composes every archived message from fixed blocks:

```text
推荐指数：⭐⭐⭐⭐⭐        ← rating block (stars)

#存档 #Archive #Nice      ← tags, space-separated

收藏的消息再也不乱啦！      ← original body

来自：                     ← source block
https://t.me/xxx/123
```

Tags are space-separated on one line; the database stores them as a structured list. A rating of `0` clears the stars and renders nothing.

## Admin commands

Commands are restricted to user ids listed under `admins` in `config.yaml`. **Reply commands** act on the archived message you reply to:

| Command | Effect |
|---|---|
| `/tag <tags…>` | Append tags (space-separated) to the replied message |
| `/rating <0-5>` | Set rating; `0` clears it |

**Direct commands** (sent anywhere the account sits):

| Command | Effect |
|---|---|
| `/status` | Runtime status (sources / targets / queue / worker) |
| `/queue` | Queue stats (pending, failed, ETA) |
| `/tags` | Tag statistics |
| `/pause` / `/resume` | Pause / resume the queue |
| `/rethumb [N]` | Backfill thumbnails for the N most recent messages (default 100) |
| `/id` | Print current chat / sender id |
| `/start` / `/help` | Command overview |

## Web dashboard

One process hosts both the Telegram pipeline and a FastAPI web app (Vue 3 SPA). It binds to `127.0.0.1:8000` by default; for LAN access set `WEB_HOST=0.0.0.0` in `.env` and open `http://<lan-ip>:8000` (make sure the port is open in your firewall). Sessions are cookie-based and must re-login after a process restart. If you expose it beyond your LAN, put Nginx / Caddy in front with HTTPS.

<!-- Screenshot placeholder: dashboard / message detail editing -->

| Page | What it does |
|---|---|
| Dashboard | Runtime stats overview |
| Messages | Browse archived messages with thumbnails; filter by keyword (matches original and rendered text), tags (multiple tags AND together), rating, media type, target channel; open a message to edit its rating and tags — saved edits re-render and sync back to Telegram |
| Tags | Tag statistics |
| Settings | Config editor (auto-backup on save, restart to apply), config / database backup, download, restore, import, and database reset |

Two UI themes — `minimal` (简约风, the default) and `collection` (素材志) — each with selectable accent palettes; display mode supports light / dark / follow-system.

**Scheduled auto-backup**: the database is backed up automatically every 1 / 3 / 7 (default) / 30 days while the app runs (missed schedules run on next startup); local retention count is configurable, and backups can also be uploaded to a Telegram chat of your choice.

### Running locally

The default `.env` already enables the dashboard, so `python -m app` is all you need. To work on the web backend alone (no Telegram connection; write endpoints return 503):

```bash
python -m app.web.devserver
```

### Docker

```bash
# 1. First login: interactive phone → code → 2FA, creates the session file
docker compose run --rm app python -m app.auth

# 2. Run (the frontend is built into the image via a multi-stage build; no local Node needed)
docker compose up -d
```

Compose maps `WEB_PORT` and mounts `config.yaml` (read-only), `telegram_archive.session`, `archive.sqlite`, `logs/` and `thumbs/`. Set `WEB_HOST=0.0.0.0` in `.env` for the container to serve external traffic.

## Data & backup

| File | Notes |
|---|---|
| `telegram_archive.session` | Telegram login state; back it up manually when migrating servers (never committed) |
| `archive.sqlite` | All structured data; one-click backup from the web UI |
| `logs/` | Log directory |
| `thumbs/` | Thumbnail cache; rebuild anytime with `/rethumb` |

The database schema is managed by SQL migrations in `migrations/`, applied automatically at startup.

## Development

Backend (Python 3.11+):

```bash
pip install -r requirements-dev.txt
ruff check app tests     # lint
pytest                   # full test suite (~160 cases)
```

Frontend (`web/`, pnpm + Node 22):

```bash
cd web
pnpm install --frozen-lockfile
pnpm dev        # Vite dev server on :5173, /api proxied to 127.0.0.1:8000
pnpm test       # Vitest
pnpm lint       # ESLint
pnpm build      # vue-tsc type check + production build
```

CI (GitHub Actions) runs `ruff check` + `pytest` (Python 3.12) for the backend, and `pnpm lint` + `pnpm test` + `pnpm build` (Node 22) for the frontend.

## Project layout

```text
app/                  # Python backend (Telethon + FastAPI)
  processor/          #   event handling: new messages, reply commands, edit/delete mirroring
  queue/              #   send queue: rate limiting, retries, restart recovery
  renderer/           #   archived message rendering
  tags/               #   tag engine and pinned per-channel tag index
  telegram/           #   client construction and message copying
  media/              #   thumbnails and backfill
  web/                #   FastAPI app, auth, config editor, backups
migrations/           # SQLite migrations
web/                  # Vue 3 + Tailwind SPA
tests/                # pytest suite
```

## FAQ

**Is this a Bot API bot?**
No. It runs as a user account via Telethon (`TELEGRAM_BOT_TOKEN` is reserved only). Use a dedicated account and make it an admin of your target channels.

**Does media get downloaded to my server?**
Never. Archiving uses Telegram's copy-by-reference, so media stays in Telegram. Only small browsing thumbnails are cached locally.

**If I edit tags or a rating in the web UI, does the Telegram message change?**
Yes. Saving writes to the database, re-renders, and edits the message — plus the pinned tag index — in the target channel. Edits and deletes made in Telegram mirror back the same way.

**Why didn't my `config.yaml` change take effect?**
Edits made through the web config editor require a process restart to apply (a `config.yaml.bak` backup is written on save). Rendering settings like `message_template` only affect messages archived afterwards.

**What if the process dies mid-queue?**
On startup the queue resets interrupted `processing` items back to `pending` and continues sending.

**I forgot the web password.**
Set a new `WEB_TOKEN` in `.env` and restart; browser sessions are invalidated by the restart anyway.

## License

[MIT](../../LICENSE) © 2026 VenenoSix24
