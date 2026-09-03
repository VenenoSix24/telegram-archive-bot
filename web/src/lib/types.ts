export type MediaType =
  | 'photo'
  | 'video'
  | 'document'
  | 'audio'
  | 'voice'
  | 'sticker'
  | 'text'
  | 'other'

export type TagType = 'source' | 'original' | 'manual'

export interface MessageTag {
  name: string
  type: TagType
}

export interface MessageTarget {
  id: number | null
  chat_id: number
  message_id: number | null
  url: string | null
  status: string
  original_text: string
  original_html: string
  rendered_text: string
  rating: number
  tags: MessageTag[]
  name?: string
}

export interface Message {
  id: number
  material_id: string
  target_id?: number | null
  source_chat_id: number
  source_message_id: number
  target_chat_id: number | null
  target_message_id: number | null
  targets: MessageTarget[]
  media_type: MediaType
  media_group_id: string | null
  original_text: string
  original_html: string
  rendered_text: string
  rating: number
  source_url: string | null
  target_url: string | null
  file_name: string | null
  file_size: number | null
  duration: number | null
  status: string
  created_at: string
  tags: MessageTag[]
}

export interface MessagesResponse {
  items: Message[]
  total: number
  limit: number
  offset: number
}

export interface Target {
  chat_id: number
  count: number
  /** 配置里的人读名称；缺失为空串，前端回退拼 ID */
  name?: string
}

export interface BackupItem {
  name: string
  kind: 'config' | 'database'
  size: number
  created_at: string
}

export interface EditableConfig {
  source_chats: {
    chat_id: number | null
    name: string
    default_tags: string[]
    target_channel_ids: number[]
    private: boolean
  }[]
  target_channels: { chat_id: number | null; name: string; private: boolean }[]
  forward_interval: number
  retry_count: number
  show_link: boolean
  preserve_original: boolean
  rating_enabled: boolean
  admins: number[]
  thumbnail_media: 'first_video' | 'first'
  thumbnail_source: 'auto' | 'archive' | 'source'
  message_template: string[]
}

export interface Stats {
  messages: {
    total: number
    archived: number
    sources: number
    by_type: Record<string, number>
  }
  tags: { total: number; with_messages: number }
  queue: Record<string, number>
  targets: Target[]
}

export interface TagCount {
  name: string
  count: number
}

export interface TagsResponse {
  items: TagCount[]
  total: number
}

/** 近 N 天归档趋势的单日点：date 为本地日 ISO 文本（YYYY-MM-DD） */
export interface TrendPoint {
  date: string
  count: number
}

export interface TrendResponse {
  items: TrendPoint[]
}