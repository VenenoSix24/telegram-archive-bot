-- Preserve Telegram formatting separately from searchable plain text.
ALTER TABLE messages ADD COLUMN original_html TEXT NOT NULL DEFAULT '';
