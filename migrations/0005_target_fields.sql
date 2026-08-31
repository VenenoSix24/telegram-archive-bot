ALTER TABLE message_targets ADD COLUMN rating INTEGER NOT NULL DEFAULT 0;
ALTER TABLE message_targets ADD COLUMN original_text TEXT NOT NULL DEFAULT '';
ALTER TABLE message_targets ADD COLUMN original_html TEXT NOT NULL DEFAULT '';
ALTER TABLE message_targets ADD COLUMN rendered_text TEXT NOT NULL DEFAULT '';
ALTER TABLE message_targets ADD COLUMN thumb_path TEXT;

CREATE TABLE IF NOT EXISTS target_tags (
    target_id INTEGER NOT NULL REFERENCES message_targets(id) ON DELETE CASCADE,
    tag_id INTEGER NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
    type TEXT NOT NULL,
    PRIMARY KEY (target_id, tag_id)
);

CREATE INDEX IF NOT EXISTS idx_target_tags_tag ON target_tags(tag_id);
