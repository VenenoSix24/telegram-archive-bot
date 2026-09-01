ALTER TABLE messages ADD COLUMN template_layout TEXT NOT NULL DEFAULT '["rating","tags","body","source"]';
ALTER TABLE message_targets ADD COLUMN template_layout TEXT NOT NULL DEFAULT '["rating","tags","body","source"]';
