-- 0009_fts_search: FTS5 全文索引（external-content over messages）。
-- 索引列取 messages 的真实文本列（original_text/rendered_text/file_name，
-- file_name 由 0002 引入）。content_rowid=id 与 messages 主键对齐；
-- 用 AFTER 触发器增量同步，迁移末尾 rebuild 一次性为存量行建索引。
-- 若 SQLite 编译未带 FTS5，本迁移会在 CREATE VIRTUAL TABLE 处报错；
-- 查询层对 MATCH 失败（表缺失/语法错误）回退到原 LIKE 路径，搜索不 500。

CREATE VIRTUAL TABLE IF NOT EXISTS messages_fts USING fts5(
    original_text,
    rendered_text,
    file_name,
    content='messages',
    content_rowid='id',
    tokenize='trigram'
);

CREATE TRIGGER IF NOT EXISTS messages_fts_ai AFTER INSERT ON messages BEGIN
    INSERT INTO messages_fts(rowid, original_text, rendered_text, file_name)
    VALUES (new.id, new.original_text, new.rendered_text, new.file_name);
END;

CREATE TRIGGER IF NOT EXISTS messages_fts_au AFTER UPDATE ON messages BEGIN
    INSERT INTO messages_fts(messages_fts, rowid, original_text, rendered_text, file_name)
    VALUES ('delete', old.id, old.original_text, old.rendered_text, old.file_name);
    INSERT INTO messages_fts(rowid, original_text, rendered_text, file_name)
    VALUES (new.id, new.original_text, new.rendered_text, new.file_name);
END;

CREATE TRIGGER IF NOT EXISTS messages_fts_ad AFTER DELETE ON messages BEGIN
    INSERT INTO messages_fts(messages_fts, rowid, original_text, rendered_text, file_name)
    VALUES ('delete', old.id, old.original_text, old.rendered_text, old.file_name);
END;

-- 为迁移前已存在的行建索引（幂等：rebuild 全量重建）。
INSERT INTO messages_fts(messages_fts) VALUES ('rebuild');

-- 副本（message_targets）有独立的 original_text / rendered_text（0005 引入），
-- joined 列表主路径搜的是副本文本，因此同样建 FTS 索引并触发器同步；
-- 查询层把两张表的命中取并集。
CREATE VIRTUAL TABLE IF NOT EXISTS message_targets_fts USING fts5(
    original_text,
    rendered_text,
    content='message_targets',
    content_rowid='id',
    tokenize='trigram'
);

CREATE TRIGGER IF NOT EXISTS message_targets_fts_ai AFTER INSERT ON message_targets BEGIN
    INSERT INTO message_targets_fts(rowid, original_text, rendered_text)
    VALUES (new.id, new.original_text, new.rendered_text);
END;

CREATE TRIGGER IF NOT EXISTS message_targets_fts_au AFTER UPDATE ON message_targets BEGIN
    INSERT INTO message_targets_fts(message_targets_fts, rowid, original_text, rendered_text)
    VALUES ('delete', old.id, old.original_text, old.rendered_text);
    INSERT INTO message_targets_fts(rowid, original_text, rendered_text)
    VALUES (new.id, new.original_text, new.rendered_text);
END;

CREATE TRIGGER IF NOT EXISTS message_targets_fts_ad AFTER DELETE ON message_targets BEGIN
    INSERT INTO message_targets_fts(message_targets_fts, rowid, original_text, rendered_text)
    VALUES ('delete', old.id, old.original_text, old.rendered_text);
END;

INSERT INTO message_targets_fts(message_targets_fts) VALUES ('rebuild');
