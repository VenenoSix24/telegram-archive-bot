import DOMPurify from 'dompurify'

const ALLOWED_TAGS = [
  'a', 'b', 'blockquote', 'br', 'code', 'del', 'em', 'i', 'li', 'ol', 'p', 'pre', 's', 'strong', 'u', 'ul',
]

export function sanitizeTelegramHtml(html: string, fallback: string): string {
  if (!html) {
    const escaped = fallback.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    return escaped.replace(/\r?\n/g, '<br>')
  }
  return DOMPurify.sanitize(html, {
    ALLOWED_TAGS,
    ALLOWED_ATTR: ['href'],
    FORBID_ATTR: ['style', 'class', 'id'],
    ALLOW_UNKNOWN_PROTOCOLS: false,
  })
}
