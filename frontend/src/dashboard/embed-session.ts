const REFRESH_MARGIN_MS = 60_000

export const refreshDelayMs = (expiresAt: string, now = Date.now()): number => {
  const expires = Date.parse(expiresAt)
  if (Number.isNaN(expires)) {
    return 0
  }
  return Math.max(expires - now - REFRESH_MARGIN_MS, 0)
}
