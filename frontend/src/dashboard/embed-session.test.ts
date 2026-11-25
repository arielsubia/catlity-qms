import { describe, expect, it } from 'vitest'

import { refreshDelayMs } from './embed-session'

describe('refreshDelayMs', () => {
  it('asks again one minute before a 15-minute session ends', () => {
    const now = Date.parse('2026-11-25T12:00:00.000Z')
    const expiresAt = '2026-11-25T12:15:00.000Z'

    expect(refreshDelayMs(expiresAt, now)).toBe(14 * 60 * 1000)
  })

  it('does not schedule a wait when the session is already inside the last minute', () => {
    const now = Date.parse('2026-11-25T12:14:30.000Z')

    expect(refreshDelayMs('2026-11-25T12:15:00.000Z', now)).toBe(0)
  })
})
