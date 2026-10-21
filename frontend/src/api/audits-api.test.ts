import { fetchAuthSession } from 'aws-amplify/auth'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from './http'
import { createAudit, listAudits, updateAuditStatus } from './audits-api'

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

describe('audits api', () => {
  beforeEach(() => {
    fetchMock.mockReset()
    vi.stubGlobal('fetch', fetchMock)
    vi.mocked(fetchAuthSession).mockResolvedValue({
      tokens: { idToken: { toString: () => 'id-token' } },
    } as Awaited<ReturnType<typeof fetchAuthSession>>)
  })

  it('lists audits with the id token and the status query', async () => {
    fetchMock.mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ items: [], total: 0, skip: 0, limit: 10 }),
    })

    await listAudits({ skip: 10, limit: 10, status: 'planned' })

    expect(fetchMock).toHaveBeenCalledWith(
      'http://api.test/api/v1/audits/?skip=10&limit=10&status=planned',
      expect.objectContaining({
        headers: expect.any(Headers),
      }),
    )
    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit]
    expect(new Headers(init.headers).get('Authorization')).toBe('Bearer id-token')
  })

  it('creates an audit with the API field names', async () => {
    fetchMock.mockResolvedValue({
      ok: true,
      status: 201,
      json: async () => ({ id: 'audit-1' }),
    })

    await createAudit({
      title: 'Line audit',
      description: null,
      auditType: 'internal',
      plannedDate: '2026-12-01',
    })

    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit]
    expect(init.method).toBe('POST')
    expect(init.body).toBe(
      JSON.stringify({
        title: 'Line audit',
        description: null,
        audit_type: 'internal',
        planned_date: '2026-12-01',
      }),
    )
  })

  it('surfaces the API error detail', async () => {
    fetchMock.mockResolvedValue({
      ok: false,
      status: 403,
      json: async () => ({ detail: 'Only the assigned auditor can change this audit' }),
    })

    await expect(updateAuditStatus('audit-1', 'in_progress')).rejects.toEqual(
      expect.objectContaining({
        message: 'Only the assigned auditor can change this audit',
        status: 403,
      }),
    )
  })

  it('reports that the API is unreachable', async () => {
    fetchMock.mockRejectedValue(new Error('offline'))

    await expect(listAudits({ skip: 0, limit: 10 })).rejects.toBeInstanceOf(ApiError)
    await expect(listAudits({ skip: 0, limit: 10 })).rejects.toThrow(
      'Could not reach the API. Check that the backend is running.',
    )
  })
})
