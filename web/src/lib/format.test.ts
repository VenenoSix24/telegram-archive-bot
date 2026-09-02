import { describe, expect, it } from 'vitest'
import { durationLabel, formatTime, ratioLabel, shortDate, splitBodyTitleDesc } from '@/lib/format'

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

describe('shortDate', () => {
  it('keeps the MM-DD part', () => {
    expect(shortDate('2026-08-30 04:05:00')).toBe('08-30')
  })

  it('returns empty for null and junk', () => {
    expect(shortDate(null)).toBe('')
    expect(shortDate('junk')).toBe('')
  })
})

describe('ratioLabel', () => {
  it('reduces common aspect ratios', () => {
    expect(ratioLabel(1920, 1080)).toBe('16:9')
    expect(ratioLabel(3264, 2448)).toBe('4:3')
    expect(ratioLabel(1080, 1920)).toBe('9:16')
    expect(ratioLabel(240, 240)).toBe('1:1')
  })

  it('returns empty for extreme ratios and bad input', () => {
    expect(ratioLabel(1170, 2532)).toBe('')
    expect(ratioLabel(0, 100)).toBe('')
    expect(ratioLabel(null, 100)).toBe('')
  })
})

describe('splitBodyTitleDesc', () => {
  const tags = ['游戏', 'MOD']

  it('strips template skeleton lines for display', () => {
    const text = [
      '推荐指数：⭐⭐⭐⭐',
      '#游戏 #MOD',
      '赛博朋克 2077 画质增强 MOD',
      '把路径追踪开销压到可接受范围。',
      '',
      '来自：',
      'https://t.me/sg_game/172',
    ].join('\n')
    const out = splitBodyTitleDesc(text, tags)
    expect(out.title).toBe('赛博朋克 2077 画质增强 MOD')
    expect(out.desc).toBe('把路径追踪开销压到可接受范围。')
    expect(out.body).not.toContain('推荐指数')
    expect(out.body).not.toContain('t.me')
  })

  it('strips a single-line source block', () => {
    const out = splitBodyTitleDesc('标题行\n来自：https://t.me/x/1', [])
    expect(out.title).toBe('标题行')
    expect(out.desc).toBe('')
  })

  it('keeps body lines that merely start with # but are not tag lines', () => {
    const out = splitBodyTitleDesc('#话题 后续讨论\n正文', tags)
    expect(out.title).toBe('#话题 后续讨论')
  })

  it('truncates long titles and descriptions', () => {
    const long = '字'.repeat(60)
    const out = splitBodyTitleDesc(`${long}\n${'摘'.repeat(200)}`, [])
    expect(out.title).toBe('字'.repeat(42) + '…')
    expect(out.desc).toBe('摘'.repeat(160) + '…')
  })

  it('returns empty parts for null or skeleton-only text', () => {
    expect(splitBodyTitleDesc(null, []).title).toBe('')
    const out = splitBodyTitleDesc('推荐指数：⭐⭐\n#游戏', tags)
    expect(out.title).toBe('')
    expect(out.body).toBe('')
  })
})