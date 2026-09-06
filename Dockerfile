# --- 阶段一：构建前端 SPA（web/dist 由 Vite 产出） ---
FROM node:22-alpine AS web-builder
WORKDIR /src/web
COPY web/package.json web/pnpm-lock.yaml ./
RUN corepack enable && pnpm install --frozen-lockfile
COPY web/ ./
RUN pnpm build

# --- 阶段二：Python 运行时（Telethon 归档 + FastAPI 托管 SPA） ---
FROM python:3.12-slim
WORKDIR /app

# 依赖单独拷贝以利用层缓存；Telethon 全家桶均为纯 wheel，无需编译工具链
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY migrations ./migrations
COPY --from=web-builder /src/web/dist ./web/dist

ENV PYTHONUNBUFFERED=1 \
    # 容器内所有派生文件（session / SQLite / WAL / logs / thumbs / 备份）
    # 都锚定配置文件所在目录，因此把配置指到唯一挂载卷 /app/data
    ARCHIVE_CONFIG=/app/data/config.yaml \
    # 容器内必须绑 0.0.0.0 才能映射到宿主机
    WEB_HOST=0.0.0.0

# 数据目录归运行用户所有；代码目录只读
RUN useradd --uid 1000 --create-home archiver \
    && mkdir -p /app/data \
    && chown -R archiver:archiver /app/data
USER archiver

VOLUME ["/app/data"]

# /health 不走鉴权，检查进程与数据库可达性
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:%s/health' % os.environ.get('WEB_PORT', '8000'), timeout=4)"

CMD ["python", "-m", "app"]
