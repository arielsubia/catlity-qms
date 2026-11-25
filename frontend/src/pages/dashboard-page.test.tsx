import { render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '../api/http'
import { getEmbedUrl } from '../api/quicksight-api'
import { AuthContext, type AuthContextValue } from '../auth/auth-context'
import { DashboardPage } from './dashboard-page'

vi.mock('../api/quicksight-api', () => ({
  getEmbedUrl: vi.fn(),
}))

const renderPage = (role: string) => {
  const value: AuthContextValue = {
    user: { email: 'ana@acme.com', tenantId: 'tenant-acme', role },
    signIn: vi.fn(),
    signOut: vi.fn(),
  }
  render(
    <AuthContext.Provider value={value}>
      <DashboardPage />
    </AuthContext.Provider>,
  )
}

describe('DashboardPage', () => {
  beforeEach(() => {
    vi.mocked(getEmbedUrl).mockReset()
  })

  it.each(['admin', 'qa_manager'])('shows the dashboard in an iframe for %s', async (role) => {
    vi.mocked(getEmbedUrl).mockResolvedValue({
      embed_url: 'https://quicksight.aws.example/embed/one',
      expires_at: new Date(Date.now() + 15 * 60 * 1000).toISOString(),
    })

    renderPage(role)

    expect(await screen.findByTitle('Compliance dashboard')).toHaveAttribute(
      'src',
      'https://quicksight.aws.example/embed/one',
    )
    expect(screen.getByTitle('Compliance dashboard')).toHaveClass('dashboard-frame')
    expect(screen.queryByText('This section is not available yet.')).not.toBeInTheDocument()
  })

  it('replaces the iframe before the URL expires', async () => {
    vi.mocked(getEmbedUrl)
      .mockResolvedValueOnce({
        embed_url: 'https://quicksight.aws.example/embed/one',
        expires_at: new Date(Date.now() + 61_000).toISOString(),
      })
      .mockResolvedValueOnce({
        embed_url: 'https://quicksight.aws.example/embed/two',
        expires_at: new Date(Date.now() + 15 * 60 * 1000).toISOString(),
      })

    renderPage('admin')

    expect(await screen.findByTitle('Compliance dashboard')).toHaveAttribute(
      'src',
      'https://quicksight.aws.example/embed/one',
    )

    await waitFor(
      () => {
        expect(screen.getByTitle('Compliance dashboard')).toHaveAttribute(
          'src',
          'https://quicksight.aws.example/embed/two',
        )
      },
      { timeout: 3000 },
    )
    expect(getEmbedUrl).toHaveBeenCalledTimes(2)
  })

  it('keeps the current iframe when the next URL fails', async () => {
    vi.mocked(getEmbedUrl)
      .mockResolvedValueOnce({
        embed_url: 'https://quicksight.aws.example/embed/one',
        expires_at: new Date(Date.now() + 61_000).toISOString(),
      })
      .mockRejectedValueOnce(new ApiError('Dashboard is not available yet.', 503))

    renderPage('admin')

    expect(await screen.findByTitle('Compliance dashboard')).toHaveAttribute(
      'src',
      'https://quicksight.aws.example/embed/one',
    )

    await waitFor(
      () => {
        expect(getEmbedUrl).toHaveBeenCalledTimes(2)
      },
      { timeout: 3000 },
    )
    expect(screen.getByTitle('Compliance dashboard')).toHaveAttribute(
      'src',
      'https://quicksight.aws.example/embed/one',
    )
    expect(screen.queryByText('Dashboard is not available yet.')).not.toBeInTheDocument()
  })

  it('shows that the dashboard is not available when the first URL fails', async () => {
    vi.mocked(getEmbedUrl).mockRejectedValue(new ApiError('Dashboard is not available yet.', 503))

    renderPage('qa_manager')

    expect(await screen.findByText('Dashboard is not available yet.')).toBeInTheDocument()
    expect(screen.queryByTitle('Compliance dashboard')).not.toBeInTheDocument()
  })

  it.each(['auditor', 'lead_auditor', 'auditee'])(
    'hides the iframe from %s and does not request a URL',
    (role) => {
      renderPage(role)

      expect(screen.getByRole('heading', { level: 2, name: 'Dashboard' })).toBeInTheDocument()
      expect(screen.getByText('This section is not available yet.')).toBeInTheDocument()
      expect(screen.queryByTitle('Compliance dashboard')).not.toBeInTheDocument()
      expect(getEmbedUrl).not.toHaveBeenCalled()
    },
  )
})
