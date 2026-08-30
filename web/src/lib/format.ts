/** 时长秒数 → mm:ss；null 返回空串。 */
export function durationLabel(duration: number | null): string {
  if (duration === null) return ''
  const m = Math.floor(duration / 60)
  const s = duration % 60
  return `${m}:${String(s).padStart(2, '0')}`
}

/** 人类可读文件大小；null 返回空串。 */
export function sizeLabel(bytes: number | null): string {
  if (bytes === null) return ''
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}