import { fetchAuthSession } from 'aws-amplify/auth'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from './http'
import { createFinding, listFindings, updateFinding, updateFindingStatus } from './findings-api'

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

const draft = {
  title: 'Missing record',
  description: null,
  findingType: 'major_nc',
  severity: 'medium',
  clauseReference: '8.5.1',
}

describe('findings api', () => {
  beforeEach(() => {
    fetchMock.mockReset()
    vi.stubGlobal('fetch', fetchMock)
    vi.mocked(fetchAuthSession).mockResolvedValue({
      tokens: { idToken: { toString: () => 'id-token' } },
    } as Awaited<ReturnType<typeof fetchAuthSession>>)
  })

  it('lists findings with the id token and the open count query', async () => {
    fetchMock.mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ items: [], total: 4, skip: 0, limit: 1 }),
    })

    await listFindings({ skip: 0, limit: 1, status: 'open' })

    expect(fetchMock).toHaveBeenCalledWith(
      'http://api.test/api/v1/findings?skip=0&limit=1&status=open',
      expect.objectContaining({
        headers: expect.any(Headers),
      }),
    )
    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit]
    expect(new Headers(init.headers).get('Authorization')).toBe('Bearer id-token')
  })

  it('lists findings with the type query', async () => {
    fetchMock.mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ items: [], total: 0, skip: 10, limit: 10 }),
    })

    await listFindings({ skip: 10, limit: 10, findingType: 'minor_nc' })

    expect(fetchMock).toHaveBeenCalledWith(
      'http://api.test/api/v1/findings?skip=10&limit=10&finding_type=minor_nc',
      expect.any(Object),
    )
  })

  it('creates a finding on the selected audit', async () => {
    fetchMock.mockResolvedValue({
      ok: true,
      status: 201,
      json: async () => ({ id: 'finding-1' }),
    })

    await createFinding('audit-1', draft)

    expect(fetchMock).toHaveBeenCalledWith(
      'http://api.test/api/v1/audits/audit-1/findings',
      expect.objectContaining({ method: 'POST' }),
    )
    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit]
    expect(init.body).toBe(
      JSON.stringify({
        title: 'Missing record',
        description: null,
        finding_type: 'major_nc',
        severity: 'medium',
        clause_reference: '8.5.1',
      }),
    )
  })

  it('patches descriptive fields and status on separate routes', async () => {
    fetchMock.mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ id: 'finding-1' }),
    })

    await updateFinding('finding-1', draft)
    await updateFindingStatus('finding-1', 'verified')

    const [updateUrl, updateInit] = fetchMock.mock.calls[0] as [string, RequestInit]
    const [statusUrl, statusInit] = fetchMock.mock.calls[1] as [string, RequestInit]
    expect(updateUrl).toBe('http://api.test/api/v1/findings/finding-1')
    expect(updateInit.method).toBe('PATCH')
    expect(updateInit.body).not.toContain('status')
    expect(updateInit.body).not.toContain('assignee_id')
    expect(updateInit.body).not.toContain('audit_id')
    expect(statusUrl).toBe('http://api.test/api/v1/findings/finding-1/status')
    expect(statusInit.method).toBe('PATCH')
    expect(statusInit.body).toBe(JSON.stringify({ status: 'verified' }))
  })

  it('surfaces the API error detail', async () => {
    fetchMock.mockResolvedValue({
      ok: false,
      status: 403,
      json: async () => ({ detail: "You cannot change this finding's status" }),
    })

    await expect(updateFindingStatus('finding-1', 'in_progress')).rejects.toEqual(
      expect.objectContaining({
        message: "You cannot change this finding's status",
        status: 403,
      }),
    )
  })

  it('reports that the API is unreachable', async () => {
    fetchMock.mockRejectedValue(new Error('offline'))

    await expect(listFindings({ skip: 0, limit: 10 })).rejects.toBeInstanceOf(ApiError)
    await expect(listFindings({ skip: 0, limit: 10 })).rejects.toThrow(
      'Could not reach the API. Check that the backend is running.',
    )
  })
})
