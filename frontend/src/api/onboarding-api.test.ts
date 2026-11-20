import { fetchAuthSession } from 'aws-amplify/auth'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { startOnboarding } from './onboarding-api'

vi.mock('aws-amplify/auth', () => ({
  fetchAuthSession: vi.fn(),
}))

vi.mock('../config/env', () => ({
  appConfig: {
    apiBaseUrl: 'http://api.test',
    cognitoUserPoolId: 'pool',
    cognitoAppClientId: 'client',
  },
}))

const fetchMock = vi.fn()

describe('onboarding api', () => {
  beforeEach(() => {
    fetchMock.mockReset()
    vi.stubGlobal('fetch', fetchMock)
    vi.mocked(fetchAuthSession).mockReset()
  })

  it('opens a session without an id token', async () => {
    fetchMock.mockResolvedValue({
      ok: true,
      status: 201,
      json: async () => ({
        session_id: 'session-1',
        reply: 'Send the organization name and the industry, separated by a comma.',
        industry_selected: false,
        kb_assigned: false,
        checklists_created: false,
        admin_created: false,
        knowledge_base_ids: null,
        tenant_id: null,
      }),
    })

    const result = await startOnboarding()

    expect(result.session_id).toBe('session-1')
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit]
    expect(url).toBe('http://api.test/api/v1/onboarding/start')
    expect(init.method).toBe('POST')
    expect(new Headers(init.headers).get('Authorization')).toBeNull()
    expect(fetchAuthSession).not.toHaveBeenCalled()
  })
})
