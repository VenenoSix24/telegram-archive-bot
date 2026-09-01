ALTER TABLE messages ADD COLUMN template_layout TEXT DEFAULT NULL;
ALTER TABLE message_targets ADD COLUMN template_layout TEXT DEFAULT NULL;
