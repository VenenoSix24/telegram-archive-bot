-- 后台任务失败记录：备份/上传/索引等常驻任务失败时落一条，
-- 供 /health 展示最近一次失败；写入侧按上限裁剪，防止无限增长。
CREATE TABLE IF NOT EXISTS task_failures (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task TEXT NOT NULL,
    error TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
