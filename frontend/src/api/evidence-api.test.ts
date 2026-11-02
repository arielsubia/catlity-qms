import { fetchAuthSession } from 'aws-amplify/auth'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import {
  contentTypeFor,
  listFindingEvidence,
  putEvidenceFile,
  requestDownloadUrl,
  uploadAndLink,
} from './evidence-api'
import { ApiError } from './http'

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

const pdf = new File(['hello'], 'note.pdf', { type: 'application/pdf' })

const linked = {
  id: 'link-1',
  tenant_id: 'tenant-acme',
  finding_id: 'finding-1',
  evidence_id: 'evidence-1',
  file_name: 'note.pdf',
  content_type: 'application/pdf',
  file_size: 5,
  s3_key: 'tenant-acme/evidence-1/note.pdf',
  status: 'uploaded',
  uploaded_by: 'user-1',
  uploaded_at: '2026-11-02T00:00:00Z',
  linked_by: 'user-1',
  created_at: '2026-11-02T00:00:00Z',
}

describe('evidence api', () => {
  beforeEach(() => {
    vi.unstubAllGlobals()
    fetchMock.mockReset()
    vi.stubGlobal('fetch', fetchMock)
    vi.mocked(fetchAuthSession).mockResolvedValue({
      tokens: { idToken: { toString: () => 'id-token' } },
    } as Awaited<ReturnType<typeof fetchAuthSession>>)
  })

  it('maps an allowed extension when the browser omits the type', () => {
    const docx = new File(['x'], 'report.docx', { type: '' })
    expect(contentTypeFor(docx)).toBe(
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    )
    expect(contentTypeFor(new File(['x'], 'script.exe', { type: '' }))).toBeNull()
    expect(contentTypeFor(new File(['x'], 'note.pdf', { type: 'text/plain' }))).toBeNull()
  })

  it('puts the file and reports progress without setting Content-Length', async () => {
    const headers: Record<string, string> = {}
    let progress = 0

    class FakeXHR {
      upload = {
        onprogress: null as
          ((event: { lengthComputable: boolean; loaded: number; total: number }) => void) | null,
      }
      status = 200
      onload: (() => void) | null = null
      onerror: (() => void) | null = null
      open = vi.fn()
      setRequestHeader = (name: string, value: string) => {
        headers[name] = value
      }
      send = () => {
        this.upload.onprogress?.({ lengthComputable: true, loaded: 5, total: 10 })
        this.onload?.()
      }
    }

    vi.stubGlobal('XMLHttpRequest', FakeXHR)
    await putEvidenceFile(
      'https://signed.example/note.pdf',
      pdf,
      {
        'Content-Type': 'application/pdf',
        'Content-Length': '5',
        'x-amz-storage-class': 'INTELLIGENT_TIERING',
      },
      (percent) => {
        progress = percent
      },
    )

    expect(headers).toEqual({
      'Content-Type': 'application/pdf',
      'x-amz-storage-class': 'INTELLIGENT_TIERING',
    })
    expect(progress).toBe(50)
  })

  it('signs, uploads, confirms, and links in that order', async () => {
    const calls: string[] = []
    class FakeXHR {
      upload = { onprogress: null as (() => void) | null }
      status = 200
      onload: (() => void) | null = null
      onerror: (() => void) | null = null
      open = () => {
        calls.push('PUT')
      }
      setRequestHeader = () => undefined
      send = () => {
        this.onload?.()
      }
    }
    vi.stubGlobal('XMLHttpRequest', FakeXHR)
    fetchMock.mockImplementation(async (url: string) => {
      calls.push(url)
      if (url.endsWith('/upload-url')) {
        return {
          ok: true,
          status: 201,
          json: async () => ({
            evidence_id: 'evidence-1',
            upload_url: 'https://signed.example/note.pdf',
            expires_in: 900,
            headers: {
              'Content-Type': 'application/pdf',
              'Content-Length': '5',
              'x-amz-storage-class': 'INTELLIGENT_TIERING',
            },
            s3_key: 'tenant-acme/evidence-1/note.pdf',
          }),
        }
      }
      if (url.endsWith('/confirm')) {
        return { ok: true, status: 200, json: async () => ({ status: 'uploaded' }) }
      }
      return { ok: true, status: 201, json: async () => linked }
    })

    const progress: number[] = []
    const result = await uploadAndLink('finding-1', pdf, (percent) => {
      progress.push(percent)
    })

    expect(result.evidence_id).toBe('evidence-1')
    expect(calls.map((call) => call.replace('http://api.test', ''))).toEqual([
      '/api/v1/evidence/upload-url',
      'PUT',
      '/api/v1/evidence/evidence-1/confirm',
      '/api/v1/findings/finding-1/evidence',
    ])
    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit]
    expect(new Headers(init.headers).get('Authorization')).toBe('Bearer id-token')
    expect(JSON.parse(String(init.body))).toEqual({
      file_name: 'note.pdf',
      content_type: 'application/pdf',
      file_size: 5,
    })
  })

  it('rejects a disallowed file before calling the API', async () => {
    const exe = new File(['x'], 'script.exe', { type: 'application/octet-stream' })
    await expect(uploadAndLink('finding-1', exe, () => undefined)).rejects.toBeInstanceOf(ApiError)
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('lists finding evidence and requests a download URL', async () => {
    fetchMock
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => ({ items: [linked] }),
      })
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => ({
          evidence_id: 'evidence-1',
          download_url: 'https://download.example/note.pdf',
          expires_in: 900,
          file_name: 'note.pdf',
          content_type: 'application/pdf',
        }),
      })

    await listFindingEvidence('finding-1')
    const ticket = await requestDownloadUrl('evidence-1')

    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      'http://api.test/api/v1/findings/finding-1/evidence',
      expect.any(Object),
    )
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      'http://api.test/api/v1/evidence/evidence-1/download-url',
      expect.any(Object),
    )
    expect(ticket.download_url).toBe('https://download.example/note.pdf')
  })
})
