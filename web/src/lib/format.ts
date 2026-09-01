/** -100123456789 → 123456789：Telegram 内部频道 id 去掉 -100 前缀便于阅读。 */
export function displayChatId(value: number | null): string {
  if (value == null) return ''
  const digits = String(Math.abs(value))
  return value < 0 && digits.startsWith('100') ? digits.slice(3) : digits
}

/** 时长秒数 → MM:SS；超过一小时显示 HH:MM:SS；null 返回空串。 */
export function durationLabel(duration: number | null): string {
  if (duration === null) return ''
  const total = Math.max(0, Math.floor(duration))
  const hours = Math.floor(total / 3600)
  const minutes = Math.floor((total % 3600) / 60)
  const seconds = total % 60
  const pad = (value: number) => String(value).padStart(2, '0')
  return hours > 0 ? `${pad(hours)}:${pad(minutes)}:${pad(seconds)}` : `${pad(minutes)}:${pad(seconds)}`
}

/** 人类可读文件大小；null 返回空串。 */
export function sizeLabel(bytes: number | null): string {
  if (bytes === null) return ''
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

/**
 * SQLite `CURRENT_TIMESTAMP` 是 UTC（`YYYY-MM-DD HH:MM:SS`，无时区后缀）。
 * 按 UTC 解析后转本地时区展示，避免显示偏 8 小时的 UTC 时间。
 */
export function formatTime(sqliteUtc: string | null): string {
  if (!sqliteUtc) return ''
  const [date, time] = sqliteUtc.split(' ')
  if (!date || !time) return sqliteUtc
  // ISO 8601：date-time + Z 后缀按 UTC 解析
  const d = new Date(`${date}T${time}Z`)
  if (Number.isNaN(d.getTime())) return sqliteUtc
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}