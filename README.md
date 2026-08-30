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
# 编辑 .env 填 API_ID/API_HASH/ADMIN_IDS
# 编辑 config.yaml 填 source_chats/target_channel/relay_chat 的 chat_id

python -m app.auth   # 交互式首次登录：手机号 → 验证码 → 2FA，生成 session
python -m app        # 启动
```

> 拿到 chat_id：在中转群 / 分类群里给管理员自己发 `/id`，程序会输出当前 chat 与 sender id。

## 配置项

| 文件 | 内容 |
|---|---|
| `.env` | API 凭据、管理员 ID（不进 Git） |
| `config.yaml` | 分类群、总频道、中转群、限速、Tag/Rating 开关、搜索链接模板 |

完整字段见 [config.example.yaml](config.example.yaml)。

## 消息格式

一条归档消息由 Renderer 统一渲染，顺序固定：

```
⭐⭐⭐⭐⭐
#游戏 #GTA5 #MOD

GTA5 NVE 教程


来自：
https://t.me/xxx/123
```

Tag 用空格分隔（不换行、不连写），数据库中存结构化列表而非拼接串。

## 管理命令

管理员（`ADMIN_IDS`）在关联讨论组中回复频道消息使用：

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

## 备份

- `telegram_archive.session`：Telegram 登录态，服务器迁移时手动备份还原（不进 Git）。
- 数据库文件与 `logs/` 随 volume 持久化。

## 开发

```bash
pip install -r requirements-dev.txt
ruff check app tests
pytest
```

## License

MIT（待完善）。