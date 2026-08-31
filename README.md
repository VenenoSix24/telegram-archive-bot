# Telegram Archive Bot

> 基于 Telegram + Telethon 的个人信息归档与知识整理系统
> [English](README.en.md)

把多个分类群中的内容统一归档到总频道，通过 Tag、评级、来源索引和数据库建立可持续管理的个人知识库。

## 核心思路

- **Telegram 保存媒体**：总频道（broadcast channel + 关联讨论组）是最终阅读与展示界面。
- **数据库保存结构化信息**：消息映射、Tag、Rating、来源、状态。
- **程序连接两者**：采集 → Tag Engine → Renderer → Queue → 总频道。

媒体全程以 Telegram 引用复用，不下载到服务器再重新上传。

## 快速开始

前置：Python 3.11+、一个专用的 Telegram 小号、从 [my.telegram.org](https://my.telegram.org) 获取 API ID / Hash。

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
cp config.example.yaml config.yaml
# 编辑 .env 填 API_ID/API_HASH
# 编辑 config.yaml 填 source_chats/target_channel 的 chat_id 与 admins

python -m app.auth   # 交互式首次登录：手机号 → 验证码 → 2FA，生成 session
python -m app        # 启动
```

> 拿到 chat_id：在任一源群/目标频道给管理员自己发 `/id`，程序会输出当前 chat 与 sender id。

## 配置项

| 文件 | 内容 |
|---|---|
| `.env` | API 凭据、Web 后台相关（`WEB_ENABLED` / `WEB_HOST` / `WEB_PORT` / `WEB_TOKEN`，不进 Git） |
| `config.yaml` | 源群（含默认 Tag、可选独立目标频道）、总频道、限速、Tag/Rating 开关、搜索链接模板、admins |

完整字段见 [config.example.yaml](config.example.yaml)。

## 消息格式

一条归档消息由 Renderer 统一渲染，顺序固定：

```
推荐指数：⭐⭐⭐⭐⭐
#游戏 #GTA5 #MOD

GTA5 NVE 教程


来自：
https://t.me/xxx/123
```

Tag 用空格分隔（不换行、不连写），数据库中存结构化列表而非拼接串。

## 管理命令

管理员（config.yaml `admins`）在源群或讨论组中回复归档消息使用：

| 命令 | 作用 |
|---|---|
| `/tag GTA5 MOD` | 给被回复的归档消息加 Tag |
| `/rating 5` | 设置评级 0~5 |
| `/status` | 系统状态 |
| `/queue` | 队列统计 |
| `/pause` / `/resume` | 暂停/恢复队列 |
| `/id` | 查询 chat/sender id |

## 部署

Docker（需本机安装 Docker Desktop）：

```bash
# 1. 首次登录：交互式手机号→验证码→2FA，生成 session
docker compose run --rm app python -m app.auth
# 2. 正式启动
docker compose up -d
```

会话、数据库、日志经 compose 卷持久化（`telegram_archive.session` / `archive.sqlite` / `logs/`），重启自动恢复。

## Web 后台（V2）

同一个进程里跑着两个入口：Telegram 归档管道 + FastAPI Web（Vue 3 SPA）。

```text
127.0.0.1:8000  →  Web 后台（默认仅本机访问）
```

局域网访问时，将 `.env` 中的 `WEB_HOST` 改为 `0.0.0.0`，然后使用运行主机的局域网 IP 和 `WEB_PORT` 访问，例如 `http://192.168.x.x:8000`；同时确认系统防火墙已放行该端口。默认值保持 `127.0.0.1`，避免 Web 后台意外暴露到局域网。

- 登录用 `WEB_TOKEN`（.env 里一个强随机串），浏览器保持会话，重启需重登
- 浏览归档消息、看缩略图、搜索、按 Tag / 评级 / 媒体类型筛选
- 点开消息可**直接改评级、加 / 删 Tag**——写 DB → 重渲染 → 更新总频道里的消息与
  置顶索引，Telegram 与 Web 双向同步（DB 是唯一数据中心）
- 缩略图只存本地小图用于浏览，完整媒体始终回 Telegram 打开（不建媒体仓库）

### 本机运行

`.env` 已含 `WEB_ENABLED=true` / `WEB_HOST=127.0.0.1` / `WEB_PORT=8000` / `WEB_TOKEN`，直接：

```bash
python -m app        # 启动后访问 http://127.0.0.1:8000
```

### Docker 部署

compose 已映射 `WEB_PORT`；容器内需把 `WEB_HOST` 设为 `0.0.0.0` 才能对外：

```bash
# .env
WEB_HOST=0.0.0.0
```

```bash
docker compose up -d   # 前端已打进镜像（multi-stage），构建无需本机 Node
```

> 部署到服务器时，建议用 Caddy / Nginx 反代 + HTTPS（session cookie 走 TLS 更安全）。

## 备份

- `telegram_archive.session`：Telegram 登录态，服务器迁移时手动备份还原（不进 Git）。
- 数据库文件、`logs/`、`thumbs/`（缩略图缓存）随 volume 持久化。

## 开发

```bash
pip install -r requirements-dev.txt
ruff check app tests
pytest
```

## License

MIT（待完善）。