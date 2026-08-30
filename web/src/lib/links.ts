import type { Message } from '@/lib/types'

/**
 * 构造/解析 Telegram 链接。
 *
 * 归档频道常为私密（无 username），DB 里历史消息 target_url 可能为 None，
 * 但只要知道 target_chat_id + target_message_id 就能用 deep link
 * `t.me/c/<内部id>/<id>` 打开——前端直接构造，不再完全依赖已存字符串。
 */

/** 私密频道 deep link：-1003942965645 → t.me/c/3942965645/<id> */
export function channelUrl(chatId: number, messageId: number | null): string | null {
  if (messageId == null) return null
  if (chatId < 0) {
    const internal = String(chatId).replace('-100', '')
    return `https://t.me/c/${internal}/${messageId}`
  }
  return null // 有 username 的公开频道需要 username，交给 message 里存的 target_url
}

/** 该消息的「归档频道」链接：DB 存的 target_url 优先，缺则按 id 构造 deep link。 */
export function archiveLinkOf(m: Message): string | null {
  if (m.target_url) return m.target_url
  return channelUrl(m.target_chat_id ?? 0, m.target_message_id)
}

/** 该消息的「来源」链接。 */
export function sourceLinkOf(m: Message): string | null {
  return m.source_url
}