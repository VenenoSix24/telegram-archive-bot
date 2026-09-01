import { describe, expect, it } from 'vitest'
import { durationLabel, formatTime } from '@/lib/format'

describe('durationLabel', () => {
  it('formats seconds to mm:ss', () => {
    expect(durationLabel(95)).toBe('01:35')
    expect(durationLabel(0)).toBe('00:00')
    expect(durationLabel(600)).toBe('10:00')
    expect(durationLabel(3600)).toBe('01:00:00')
    expect(durationLabel(3661.9)).toBe('01:01:01')
  })

  it('returns empty for null', () => {
    expect(durationLabel(null)).toBe('')
  })
})

describe('formatTime', () => {
  it('parses sqlite UTC as a local-time date', () => {
    const out = formatTime('2026-08-30 04:05:00')
    // 时区跟随执行环境，只保证格式正确、可解析
    expect(out).toMatch(/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$/)
  })

  it('returns empty for null and junk', () => {
    expect(formatTime(null)).toBe('')
    expect(formatTime('not-a-date')).toBe('not-a-date')
  })
})