import { fetchAuthSession } from 'aws-amplify/auth'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { queryNormative } from './normative-api'

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

describe('normative api', () => {
  beforeEach(() => {
    fetchMock.mockReset()
    vi.stubGlobal('fetch', fetchMock)
    vi.mocked(fetchAuthSession).mockResolvedValue({
      tokens: { idToken: { toString: () => 'id-token' } },
    } as Awaited<ReturnType<typeof fetchAuthSession>>)
  })

  it('posts the question with the id token', async () => {
    fetchMock.mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({
        answer: 'The study notes do not cover this question.',
        references: [
          { document: 'iso-9001-quality-policy.txt', section: 'iso-9001-quality-policy.txt' },
        ],
      }),
    })

    const result = await queryNormative('What is a quality policy?')

    expect(result).toEqual({
      answer: 'The study notes do not cover this question.',
      references: [
        { document: 'iso-9001-quality-policy.txt', section: 'iso-9001-quality-policy.txt' },
      ],
    })
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit]
    expect(url).toBe('http://api.test/api/v1/ai/normative/query')
    expect(init.method).toBe('POST')
    expect(init.body).toBe(JSON.stringify({ question: 'What is a quality policy?' }))
    expect(new Headers(init.headers).get('Authorization')).toBe('Bearer id-token')
    expect(new Headers(init.headers).get('Content-Type')).toBe('application/json')
  })
})
