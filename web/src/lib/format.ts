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

/** MM-DD 短日期（目录图签用）；格式不符返回空串。 */
export function shortDate(sqliteUtc: string | null): string {
  if (!sqliteUtc) return ''
  const date = sqliteUtc.split(' ')[0]
  return /^\d{4}-\d{2}-\d{2}$/.test(date) ? date.slice(5) : ''
}

/** 图片宽高 → 约分后的「宽:高」标签；任一边超出 20 或参数无效返回空串。 */
export function ratioLabel(width: number | null, height: number | null): string {
  if (!width || !height || width <= 0 || height <= 0) return ''
  const gcd = (a: number, b: number): number => (b === 0 ? a : gcd(b, a % b))
  const d = gcd(width, height) || 1
  const w = Math.round(width / d)
  const h = Math.round(height / d)
  return w <= 20 && h <= 20 ? `${w}:${h}` : ''
}

/**
 * 副本正文带模板骨架（评级行 / Tag 行 / 来源块），卡片标题与摘要展示时按行
 * 剥离：只剥「整行匹配」的行，与后端 extract_edited_body 同代价——正文恰好
 * 整行相等的罕见内容会被一并隐藏。Tag 行仅在全部命中已知 Tag 时剥离，
 * 避免误伤正文里恰以 # 开头的整行。首行为标题，其余合并为摘要。
 */
export function splitBodyTitleDesc(
  text: string | null,
  knownTags: string[],
): { title: string; desc: string; body: string } {
  const rawLines = (text ?? '').split('\n').map((line) => line.trim())
  const kept: string[] = []
  for (let i = 0; i < rawLines.length; i++) {
    const line = rawLines[i]
    if (!line) continue
    if (/^推荐指数：⭐+$/.test(line)) continue
    if (/^来自：\S+$/.test(line)) continue
    if (/^https?:\/\/\S+$/.test(line)) continue
    // 「来自：」与 URL 分两行的来源块
    if (line === '来自：' && i + 1 < rawLines.length && /^https?:\/\/\S+$/.test(rawLines[i + 1])) {
      i++
      continue
    }
    const names = line.split(/\s+/).filter(Boolean)
    const isTagLine =
      names.length > 0 && names.every((name) => knownTags.includes(name.replace(/^#/, '')))
    if (isTagLine) continue
    kept.push(line)
  }
  const title = kept[0] ?? ''
  const desc = kept.slice(1).join(' ')
  return {
    title: title.length > 42 ? title.slice(0, 42) + '…' : title,
    desc: desc.length > 160 ? desc.slice(0, 160) + '…' : desc,
    body: kept.join('\n'),
  }
}