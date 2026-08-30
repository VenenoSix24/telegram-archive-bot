FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt requirements-dev.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY migrations ./migrations

ENV PYTHONUNBUFFERED=1

# 运行时配置来自挂载的 config.yaml 与 .env；session/db/logs 用卷持久化
CMD ["python", "-m", "app"]