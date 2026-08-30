# Changelog

本项目遵循 [Conventional Commits](https://www.conventionalcommits.org/) 与
[Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)。

## [Unreleased]

### Added

- Web 管理后台（V2，Vue 3 SPA + FastAPI，与 Telegram 归档管道同进程运行）：
  - 消息浏览：搜索正文、按 Tag / 评级 / 媒体类型 / 来源群筛选、分页
  - 消息详情抽屉：查看来源、在 Telegram 中打开、直接改评级、加 / 删 Tag
  - 缩略图缓存：归档时抓取小图，存量经 `/rethumb` 批量补抓，Web 首次浏览懒补
  - 媒体元数据：文件名、大小、时长落库并展示
  - 双向同步：Web 与 Telegram 的 Tag / 评级修改共用同一编辑入口，DB 为唯一数据中心
  - Web 鉴权：`WEB_TOKEN` 登录换 HttpOnly 会话，`WEB_ENABLED` / `WEB_HOST` / `WEB_PORT` 走 .env
- Docker multi-stage：前端构建并入镜像，`WEB_PORT` 端口映射
- CI：新增前端 job（pnpm lint + test + build）

### Changed

- README 双语补充 Web 后台章节，修正 V1 重构遗留的 `relay_chat` / `ADMIN_IDS` 旧表述
- `/tag` `/rating` 回复命令重构为共享编辑服务，与 Web API 行为一致

## [0.1.0] - 未打 tag

V1 SDK 阶段：自动归档闭环、Tag / Rating、置顶索引、管理命令、Docker 部署（历史记录见 git log）。