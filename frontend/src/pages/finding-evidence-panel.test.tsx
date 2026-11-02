import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import {
  listFindingEvidence,
  requestDownloadUrl,
  uploadAndLink,
  type FindingEvidence,
} from '../api/evidence-api'
import { FindingEvidencePanel } from './finding-evidence-panel'

vi.mock('../api/evidence-api', async () => {
  const actual = await vi.importActual<typeof import('../api/evidence-api')>('../api/evidence-api')
  return {
    ...actual,
    listFindingEvidence: vi.fn(),
    uploadAndLink: vi.fn(),
    requestDownloadUrl: vi.fn(),
  }
})

const evidence = (overrides: Partial<FindingEvidence> = {}): FindingEvidence => ({
  id: 'link-1',
  tenant_id: 'tenant-acme',
  finding_id: 'finding-1',
  evidence_id: 'evidence-1',
  file_name: 'gauge.pdf',
  content_type: 'application/pdf',
  file_size: 20,
  s3_key: 'tenant-acme/evidence-1/gauge.pdf',
  status: 'uploaded',
  uploaded_by: 'user-1',
  uploaded_at: '2026-11-02T00:00:00Z',
  linked_by: 'user-1',
  created_at: '2026-11-02T00:00:00Z',
  ...overrides,
})

const fileInput = (): HTMLInputElement => {
  const input = document.querySelector('input[type="file"]')
  if (!(input instanceof HTMLInputElement)) {
    throw new Error('Missing file input')
  }
  return input
}

describe('FindingEvidencePanel', () => {
  beforeEach(() => {
    vi.mocked(listFindingEvidence).mockReset()
    vi.mocked(uploadAndLink).mockReset()
    vi.mocked(requestDownloadUrl).mockReset()
    vi.mocked(listFindingEvidence).mockResolvedValue({ items: [] })
  })

  it('offers drag and drop and an empty gallery', async () => {
    render(<FindingEvidencePanel findingId="finding-1" />)

    expect(
      await screen.findByText('Drop evidence here, or click to choose a file'),
    ).toBeInTheDocument()
    expect(screen.getByText('PDF, PNG, JPG, or DOCX. Maximum 25 MB.')).toBeInTheDocument()
    expect(await screen.findByText('No files linked to this finding yet.')).toBeInTheDocument()
    expect(listFindingEvidence).toHaveBeenCalledWith('finding-1')
  })

  it('previews an image and shows a document name', async () => {
    vi.mocked(listFindingEvidence).mockResolvedValue({
      items: [
        evidence({
          id: 'link-photo',
          evidence_id: 'evidence-photo',
          file_name: 'photo.png',
          content_type: 'image/png',
        }),
        evidence(),
      ],
    })
    vi.mocked(requestDownloadUrl).mockResolvedValue({
      evidence_id: 'evidence-photo',
      download_url: 'https://download.example/photo.png',
      expires_in: 900,
      file_name: 'photo.png',
      content_type: 'image/png',
    })

    render(<FindingEvidencePanel findingId="finding-1" />)

    const preview = await screen.findByRole('img', { name: 'photo.png' })
    expect(preview).toHaveAttribute('src', 'https://download.example/photo.png')
    expect(screen.getByText('gauge.pdf')).toBeInTheDocument()
    expect(screen.getByText('photo.png')).toBeInTheDocument()
    expect(requestDownloadUrl).toHaveBeenCalledTimes(1)
    expect(requestDownloadUrl).toHaveBeenCalledWith('evidence-photo')
  })

  it('opens a presigned URL from the download button', async () => {
    const user = userEvent.setup()
    const open = vi.spyOn(window, 'open').mockImplementation(() => null)
    vi.mocked(listFindingEvidence).mockResolvedValue({ items: [evidence()] })
    vi.mocked(requestDownloadUrl).mockResolvedValue({
      evidence_id: 'evidence-1',
      download_url: 'https://download.example/gauge.pdf',
      expires_in: 900,
      file_name: 'gauge.pdf',
      content_type: 'application/pdf',
    })

    render(<FindingEvidencePanel findingId="finding-1" />)
    await user.click(await screen.findByRole('button', { name: 'Download gauge.pdf' }))

    expect(requestDownloadUrl).toHaveBeenCalledWith('evidence-1')
    expect(open).toHaveBeenCalledWith(
      'https://download.example/gauge.pdf',
      '_blank',
      'noopener,noreferrer',
    )
  })

  it('shows a progress bar while a dropped file uploads', async () => {
    const user = userEvent.setup()
    let report: (percent: number) => void = () => undefined
    vi.mocked(uploadAndLink).mockImplementation((_findingId, _file, onProgress) => {
      report = onProgress
      return new Promise<FindingEvidence>(() => undefined)
    })

    render(<FindingEvidencePanel findingId="finding-1" />)
    await screen.findByText('No files linked to this finding yet.')
    await user.upload(fileInput(), new File(['hello'], 'note.pdf', { type: 'application/pdf' }))
    report(45)

    expect(await screen.findByRole('progressbar')).toHaveAttribute('aria-valuenow', '45')
    expect(uploadAndLink).toHaveBeenCalledOnce()
  })

  it('adds the linked file to the gallery after the upload finishes', async () => {
    const user = userEvent.setup()
    vi.mocked(uploadAndLink).mockResolvedValue(evidence({ file_name: 'note.pdf' }))

    render(<FindingEvidencePanel findingId="finding-1" />)
    await screen.findByText('No files linked to this finding yet.')
    await user.upload(fileInput(), new File(['hello'], 'note.pdf', { type: 'application/pdf' }))

    const gallery = await screen.findByRole('list')
    expect(within(gallery).getByText('note.pdf')).toBeInTheDocument()
    expect(screen.queryByText('No files linked to this finding yet.')).not.toBeInTheDocument()
  })

  it('rejects a file whose type is not PDF, PNG, JPG, or DOCX', async () => {
    const user = userEvent.setup()
    render(<FindingEvidencePanel findingId="finding-1" />)
    await screen.findByText('No files linked to this finding yet.')
    await user.upload(fileInput(), new File(['x'], 'notes.pdf', { type: 'text/plain' }))

    expect(await screen.findByText('File type must be PDF, PNG, JPG, or DOCX.')).toBeInTheDocument()
    expect(uploadAndLink).not.toHaveBeenCalled()
  })

  it('rejects a file larger than 25 MB', async () => {
    const user = userEvent.setup()
    const big = new File(['x'], 'big.pdf', { type: 'application/pdf' })
    Object.defineProperty(big, 'size', { value: 25 * 1024 * 1024 + 1 })
    render(<FindingEvidencePanel findingId="finding-1" />)
    await screen.findByText('No files linked to this finding yet.')
    await user.upload(fileInput(), big)

    expect(
      await screen.findByText('File size must be between 1 byte and 25 MB.'),
    ).toBeInTheDocument()
    expect(uploadAndLink).not.toHaveBeenCalled()
  })
})
