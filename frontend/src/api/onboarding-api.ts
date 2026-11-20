import { publicApiRequest } from './http'

export interface OnboardingSession {
  session_id: string
  reply: string
  industry_selected: boolean
  kb_assigned: boolean
  checklists_created: boolean
  admin_created: boolean
  knowledge_base_ids: Record<string, string> | null
  tenant_id: string | null
}

export interface OnboardingLoginState {
  fullName: string
  email: string
}

const ADMINISTRATOR_REPLY = /Administrator: (.+) <([^<>]+)>/

export const isOnboardingLoginState = (value: unknown): value is OnboardingLoginState => {
  if (typeof value !== 'object' || value === null) {
    return false
  }
  const record = value as Record<string, unknown>
  return (
    typeof record.fullName === 'string' &&
    record.fullName.trim().length > 0 &&
    typeof record.email === 'string' &&
    record.email.includes('@')
  )
}

export const readCreatedAdministrator = (
  reply: string,
  message: string,
): OnboardingLoginState | null => {
  const matched = ADMINISTRATOR_REPLY.exec(reply)
  if (matched) {
    return { fullName: matched[1], email: matched[2] }
  }
  const comma = message.lastIndexOf(',')
  if (comma < 1) {
    return null
  }
  const fullName = message.slice(0, comma).trim()
  const email = message.slice(comma + 1).trim()
  if (!fullName || !email.includes('@')) {
    return null
  }
  return { fullName, email }
}

export const startOnboarding = (): Promise<OnboardingSession> =>
  publicApiRequest<OnboardingSession>('/api/v1/onboarding/start', { method: 'POST' })

export const sendOnboardingMessage = (
  sessionId: string,
  message: string,
): Promise<OnboardingSession> =>
  publicApiRequest<OnboardingSession>('/api/v1/onboarding/message', {
    method: 'POST',
    body: JSON.stringify({ session_id: sessionId, message }),
  })
