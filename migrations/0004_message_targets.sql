CREATE TABLE IF NOT EXISTS message_targets (
    id INTEGER PRIMARY KEY,
    message_id INTEGER NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
    target_chat_id INTEGER NOT NULL,
    target_message_id INTEGER,
    target_url TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    UNIQUE(message_id, target_chat_id)
);
CREATE INDEX IF NOT EXISTS idx_message_targets_lookup
ON message_targets(target_chat_id, target_message_id);
