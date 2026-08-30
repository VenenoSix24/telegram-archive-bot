-- 0001_initial: 核心表结构。
-- messages 以 (source_chat_id, source_message_id) 唯一约束去重；
-- Tag Alias 预留 alias_of 字段（V1 不实现合并）；
-- settings 用于保存 tag_index_message_id 等运行状态。

CREATE TABLE IF NOT EXISTS channels (
    id INTEGER PRIMARY KEY,
    chat_id INTEGER NOT NULL UNIQUE,
    name TEXT NOT NULL DEFAULT '',
    type TEXT NOT NULL,
    default_tags TEXT NOT NULL DEFAULT '[]',
    enabled INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY,
    source_chat_id INTEGER NOT NULL,
    source_message_id INTEGER NOT NULL,
    target_chat_id INTEGER,
    target_message_id INTEGER,
    media_group_id TEXT,
    media_type TEXT NOT NULL DEFAULT 'text',
    original_text TEXT NOT NULL DEFAULT '',
    rendered_text TEXT NOT NULL DEFAULT '',
    source_url TEXT,
    target_url TEXT,
    rating INTEGER NOT NULL DEFAULT 0,
    source_deleted INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'processed',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (source_chat_id, source_message_id)
);

CREATE TABLE IF NOT EXISTS tags (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    normalized_name TEXT NOT NULL,
    alias_of TEXT,
    count INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS message_tags (
    message_id INTEGER NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
    tag_id INTEGER NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
    type TEXT NOT NULL,
    PRIMARY KEY (message_id, tag_id)
);

CREATE TABLE IF NOT EXISTS queue (
    id INTEGER PRIMARY KEY,
    message_id INTEGER REFERENCES messages(id) ON DELETE CASCADE,
    status TEXT NOT NULL DEFAULT 'pending',
    retry_count INTEGER NOT NULL DEFAULT 0,
    next_run_at TEXT,
    last_error TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT
);

CREATE INDEX IF NOT EXISTS idx_messages_target ON messages(target_chat_id, target_message_id);
CREATE INDEX IF NOT EXISTS idx_queue_status ON queue(status, next_run_at);
CREATE INDEX IF NOT EXISTS idx_message_tags_tag ON message_tags(tag_id);