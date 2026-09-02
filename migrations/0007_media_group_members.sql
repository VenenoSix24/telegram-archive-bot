-- 相组成员落库：每条相册消息到达时记录 (源群, grouped_id, 消息id)，
-- 归档时按 id 精确取组，替代"扫描最近 200 条"的事后扫描——队列积压
-- 或相册较旧时扫描会找不到组，导致相册被拆散归档。
CREATE TABLE IF NOT EXISTS media_group_members (
    source_chat_id INTEGER NOT NULL,
    grouped_id TEXT NOT NULL,
    source_message_id INTEGER NOT NULL,
    PRIMARY KEY (source_chat_id, grouped_id, source_message_id)
);
