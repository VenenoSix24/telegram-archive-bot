-- 0002_media_meta: Web V2 展示所需的媒体元数据与缩略图路径。
-- 缩略图经 Telegram 抓取存本地 thumbs/ 目录（见 app/media/thumbnails.py），
-- thumb_path 只记相对路径，不把媒体本体入库（任务书 §49 不建媒体仓库）。

ALTER TABLE messages ADD COLUMN thumb_path TEXT;
ALTER TABLE messages ADD COLUMN file_name TEXT NOT NULL DEFAULT '';
ALTER TABLE messages ADD COLUMN file_size INTEGER;
ALTER TABLE messages ADD COLUMN duration INTEGER;