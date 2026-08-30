import { describe, expect, it } from 'vitest'
import { durationLabel } from '@/lib/format'

describe('durationLabel', () => {
  it('formats seconds to mm:ss', () => {
    expect(durationLabel(95)).toBe('1:35')
    expect(durationLabel(0)).toBe('0:00')
    expect(durationLabel(600)).toBe('10:00')
  })

  it('returns empty for null', () => {
    expect(durationLabel(null)).toBe('')
  })
})