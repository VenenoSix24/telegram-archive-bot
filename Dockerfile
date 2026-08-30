# --- 阶段一：构建前端 SPA（Web V2） ---
FROM node:22-alpine AS web-builder
WORKDIR /src/web
COPY web/package.json web/pnpm-lock.yaml ./
RUN corepack enable && pnpm install --frozen-lockfile
COPY web/ ./
RUN pnpm build

# --- 阶段二：Python 运行时（Telegram 归档 + Web 托管） ---
FROM python:3.12-slim
WORKDIR /app

COPY requirements.txt requirements-dev.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY migrations ./migrations
COPY --from=web-builder /src/web/dist ./web/dist

ENV PYTHONUNBUFFERED=1

# 运行时配置来自挂载的 config.yaml 与 .env；session/db/logs/thumbs 用卷持久化
CMD ["python", "-m", "app"]