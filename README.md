# Telegram Archive Bot

<p align="left">
  <!-- TODO(badge): 仓库公开后补充 CI / coverage 徽章的真实链接 -->
  <img alt="version" src="https://img.shields.io/badge/version-0.4.0-blue" />
  <img alt="python" src="https://img.shields.io/badge/python-3.11%2B-informational" />
  <img alt="vue" src="https://img.shields.io/badge/web-Vue%203%20%C2%B7%20Tailwind-42b883" />
  <img alt="license" src="https://img.shields.io/badge/license-MIT-green" />
</p>

> [English](README.en.md) ｜ 简体中文

**把 Telegram 群里的信息流，沉淀成可检索、可编辑的个人知识库。**

监听若干个源群，把新消息自动「复制引用」到你的总频道；Tag、评级、来源、正文全部写入 SQLite，并在 Telegram 与 Web 后台之间双向同步。媒体全程以 Telegram 引用复用，不下载、不转存。

<!-- 截图占位：Web 后台消息列表（浅色主题） -->
<!-- <img src="docs/screenshots/web-messages-light.png" width="720" /> -->

## 功能一览

- **自动归档**：源群新消息自动经队列复制到目标频道，限速发送、失败重试、重启自动恢复队列。
- **多对多路由**：多个源群、多个目标频道，每个源群可指定默认 Tag 与独立目标；中转群作为普通源群接入，历史消息手动转进来补 Tag 即可。
- **Tag 体系**：空格分隔的多个 Tag 存结构化列表（非拼接串）；每个目标频道维护一条**置顶 Tag 索引**，防抖自动更新。
- **评级系统**：0~5 星评级，渲染进消息头，可按评级筛选。
- **可定制的消息版式**：`message_template` 控制评级 / Tag / 正文 / 来源四个区块的顺序，删除区块即隐藏。
- **Web 后台**：Vue 3 + Tailwind SPA 与归档管道跑在同一进程。浏览、搜索、按 Tag / 评级 / 媒体类型筛选，直接改评级、增删 Tag——写库后自动重渲染并同步回 Telegram 消息与置顶索引。
- **双向跟随**：在 Telegram 里编辑或删除已归档消息，Web 与数据库同步更新。
- **缩略图**：仅为浏览生成小图存本地，完整媒体始终跳回 Telegram 打开，不建媒体仓库。
- **运维工具**：Web 后台内置配置编辑器（保存自动备份 `config.yaml.bak`）、配置 / 数据库备份与恢复、导入、重置数据库。

## 工作原理

```text
源群 A ──┐
源群 B ──┼─→ 监听 → SQLite（Tag/评级/来源/状态）→ 队列 → 复制引用 → 目标频道(们)
中转群 ──┘                                              │
                    Web 后台 (FastAPI + Vue 3 SPA) ←────┘
                    浏览 / 搜索 / 编辑 → 写库 → 重渲染 → 更新 Telegram 消息与置顶索引
```

三条设计原则：

1. **Telegram 保存媒体**：总频道就是最终阅读界面。
2. **数据库保存结构**：消息映射、Tag、评级、来源、状态，SQLite 是唯一数据中心。
3. **程序连接两者**：采集 → 队列 → 复制；编辑从任意一端发起，另一端自动跟随。

## 快速开始

前置条件：Python 3.11+、一个专用 Telegram 账号（建议小号）、在 [my.telegram.org](https://my.telegram.org) 申请的 API ID / API Hash。

```bash
# 1. 安装
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 2. 配置
cp .env.example .env
cp config.example.yaml config.yaml
# 编辑 .env：填 TELEGRAM_API_ID / TELEGRAM_API_HASH，并给 WEB_TOKEN 一个强随机串
#   （openssl rand -hex 32）
# 编辑 config.yaml：填 source_chats、target_channels 的 chat_id，以及 admins（你的用户 ID）

# 3. 首次登录（交互式：手机号 → 验证码 → 两步验证密码），生成 telegram_archive.session
python -m app.auth

# 4. 启动
python -m app
```

启动后访问 `http://127.0.0.1:8000` 进入 Web 后台，用 `WEB_TOKEN` 登录。

> **拿不到 chat_id？** 把程序账号拉进任一源群 / 目标频道，给它发 `/id`，它会回应当前会话的 chat id 和你的用户 id，填进 `config.yaml` 即可。

<!-- 截图占位：终端启动横幅 / 首次登录流程 -->

## 配置

敏感凭据只进 `.env`（不进 Git），业务配置进 `config.yaml`。可用环境变量 `ARCHIVE_CONFIG` 指定配置文件路径。

**`.env`**

| 变量 | 必填 | 说明 |
|---|---|---|
| `TELEGRAM_API_ID` / `TELEGRAM_API_HASH` | 是 | 从 [my.telegram.org](https://my.telegram.org) 获取 |
| `TELEGRAM_BOT_TOKEN` | 否 | 预留字段，当前架构使用个人账号（user-bot），非 Bot API |
| `WEB_ENABLED` | 否 | 默认 `true` |
| `WEB_HOST` | 否 | 默认 `127.0.0.1`；局域网访问改为 `0.0.0.0` |
| `WEB_PORT` | 否 | 默认 `8000` |
| `WEB_TOKEN` | `WEB_ENABLED=true` 时必填 | Web 登录口令，建议 `openssl rand -hex 32` |
| `LOG_LEVEL` | 否 | 终端日志级别 `DEBUG / INFO / WARNING`，默认 `INFO`；细节始终写 `logs/app.log` |

**`config.yaml`**

| 字段 | 说明 |
|---|---|
| `telegram.source_chats[]` | 源群列表：`chat_id`、`name`、`default_tags`；可选 `target_channel_ids` 指定独立目标（缺省归档到全部目标频道），`private` 控制是否自动补 `-100` 前缀 |
| `telegram.target_channels[]` | 目标频道列表：`chat_id`、`name` |
| `forward.interval` | 发送间隔秒数，默认 `3` |
| `forward.retry_count` | 失败最大重试次数，超限标记 failed，默认 `3` |
| `source.show_link` | 是否在归档消息里显示「来自：」来源链接，默认 `true` |
| `tags.preserve_original` | 是否保留原消息中的 hashtag，默认 `true` |
| `rating.enabled` | 是否启用评级，默认 `true` |
| `thumbnails.media` | 相册缩略图取哪条媒体：`first_video`（默认）/ `first` |
| `thumbnails.source` | 缩略图来源：`auto`（默认，归档优先回退源消息）/ `archive` / `source` |
| `message_template` | 消息区块顺序，默认 `[rating, tags, body, source]`；`body` 必须保留；改动只影响之后新归档的消息 |
| `admins` | 管理员用户 ID 列表，命令校验用 |
| `database.path` | SQLite 路径，默认 `archive.sqlite`（相对路径锚定 `config.yaml` 所在目录） |

完整字段见 [config.example.yaml](../../config.example.yaml)。

<!-- TODO(config): 旧 README 提到的「搜索链接模板」在当前 config.py / config.example.yaml 中已不存在，确认是否为已删除的遗留功能 -->

## 消息格式

一条归档消息由 Renderer 按固定结构渲染：

```text
推荐指数：⭐⭐⭐⭐⭐
#游戏 #GTA5 #MOD

GTA5 NVE 教程


来自：
https://t.me/xxx/123
```

Tag 用空格分隔（不换行、不连写），数据库存结构化列表而非拼接串；评级 0 为清除、不渲染。

## 管理命令

管理员（`config.yaml` 的 `admins`）在任意接入的会话中使用。**回复类命令**需回复某条已归档消息：

| 命令 | 作用 |
|---|---|
| `/tag <标签…>` | 给被回复的归档消息追加 Tag（空格分隔） |
| `/rating <0-5>` | 设置评级，`0` 清除 |

**直接发送的管理命令**：

| 命令 | 作用 |
|---|---|
| `/status` | 运行状态（监听 / 目标 / 队列 / Worker） |
| `/queue` | 队列概况（等待、失败、预计剩余） |
| `/tags` | Tag 统计 |
| `/pause` / `/resume` | 暂停 / 恢复队列 |
| `/rethumb [N]` | 补抓最近 N 条消息的缩略图（默认 100） |
| `/id` | 查看当前会话 id |
| `/start` / `/help` | 命令一览 |

## Web 后台

同一进程跑两个入口：Telegram 归档管道 + FastAPI Web（Vue 3 SPA）。默认只监听 `127.0.0.1:8000`；局域网访问时把 `.env` 的 `WEB_HOST` 改为 `0.0.0.0`，用 `http://<局域网IP>:8000` 访问，并放行防火墙端口。会话以 cookie 保持，进程重启后需重新登录；部署到公网建议 Nginx / Caddy 反代 + HTTPS。

<!-- 截图占位：Web 后台仪表盘 / 消息详情编辑 -->

功能：

- **仪表盘**：运行统计概览（`/api/stats`）
- **消息**：浏览归档消息与缩略图；按关键词（搜索原文与渲染文本）、Tag（多选取交集）、评级、媒体类型、目标频道筛选；详情页直接改评级、增删 Tag，保存后写库 → 重渲染 → 同步 Telegram 消息与置顶索引
- **Tags**：Tag 统计视图
- **设置**：配置编辑器（保存自动备份并提示重启生效）、配置 / 数据库的备份、下载、恢复、导入，以及重置数据库
- **双主题**：`collection`（素材志）与 `minimal` 两套主题，支持明暗模式切换

### 本机运行

`.env` 已含默认 Web 配置，直接 `python -m app` 即可。

仅调试 Web 后端（不连接 Telegram，编辑类接口返回 503）：

```bash
python -m app.web.devserver
```

### Docker 部署

```bash
# 1. 首次登录：交互式手机号 → 验证码 → 两步验证，生成 session
docker compose run --rm app python -m app.auth

# 2. 启动（前端已在 multi-stage 构建时打进镜像，本机无需 Node）
docker compose up -d
```

compose 会映射 `WEB_PORT` 并挂载 `config.yaml`（只读）、`telegram_archive.session`、`archive.sqlite`、`logs/`、`thumbs/`。容器内对外提供服务时需把 `.env` 的 `WEB_HOST` 设为 `0.0.0.0`。

## 数据与备份

| 文件 | 说明 |
|---|---|
| `telegram_archive.session` | Telegram 登录态，服务器迁移需手动备份还原，不进 Git |
| `archive.sqlite` | 全部结构化数据，Web 后台可一键备份 |
| `logs/` | 日志目录 |
| `thumbs/` | 缩略图缓存，可随时用 `/rethumb` 重建 |

数据库 schema 由 `migrations/` 下的 SQL 迁移管理，启动时自动应用，无需手动操作。

## 开发

后端（Python 3.11+）：

```bash
pip install -r requirements-dev.txt
ruff check app tests     # lint
pytest                   # 全量测试（约 160 个用例）
```

前端（`web/`，pnpm + Node 22）：

```bash
cd web
pnpm install --frozen-lockfile
pnpm dev        # Vite 开发服务器 :5173，/api 代理到 127.0.0.1:8000
pnpm test       # Vitest
pnpm lint       # ESLint
pnpm build      # vue-tsc 类型检查 + 生产构建
```

CI（GitHub Actions）对后端跑 `ruff check` + `pytest`（Python 3.12），对前端跑 `pnpm lint` + `pnpm test` + `pnpm build`（Node 22）。

## 项目结构

```text
app/                  # Python 后端（Telethon + FastAPI）
  processor/          #   事件处理：新消息、回复命令、编辑/删除跟随
  queue/              #   发送队列：限速、重试、重启恢复
  renderer/           #   归档消息渲染
  tags/               #   Tag 引擎与目标频道置顶索引
  telegram/           #   客户端构建与消息复制
  media/              #   缩略图与补抓
  web/                #   FastAPI 服务、鉴权、配置编辑、备份
migrations/           # SQLite 迁移
web/                  # Vue 3 + Tailwind 前端 SPA
tests/                # pytest 测试
```

## FAQ

**这是 Bot API 机器人吗？**
不是。它用 Telethon 以个人账号（user-bot）登录运行，`TELEGRAM_BOT_TOKEN` 仅为预留字段。请使用专用小号，并把它设为目标频道的管理员。

**媒体会被下载到服务器吗？**
不会。归档使用 Telegram 的复制引用，媒体始终留在 Telegram；本地只存浏览用的小缩略图。

**Web 后台改了 Tag/评级，Telegram 里的消息会变吗？**
会。Web 保存后写库、重渲染，并直接编辑总频道里的对应消息与置顶索引；反过来在 Telegram 里编辑/删除归档消息，数据库与 Web 也会跟随。

**改了 `config.yaml` 为什么没生效？**
通过 Web 后台的配置编辑器保存后需重启进程生效（保存时会自动备份 `config.yaml.bak`）。`message_template` 等渲染配置只影响之后新归档的消息。

**队列消息发到一半进程挂了怎么办？**
启动时队列会把中断的 `processing` 任务恢复为 `pending` 继续发送。

**忘了 Web 密码？**
重设 `.env` 里的 `WEB_TOKEN` 并重启即可；浏览器会话在进程重启后失效，需重新登录。

## License

[MIT](../../LICENSE) © 2026 VenenoSix24
