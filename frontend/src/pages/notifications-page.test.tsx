import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import {
  listNotifications,
  markAllNotificationsRead,
  markNotificationRead,
  type AppNotification,
} from '../api/notifications-api'
import { AuthContext, type AuthContextValue } from '../auth/auth-context'
import { NotificationsPage } from './notifications-page'

vi.mock('../api/notifications-api', async () => {
  const actual = await vi.importActual<typeof import('../api/notifications-api')>(
    '../api/notifications-api',
  )
  return {
    ...actual,
    listNotifications: vi.fn(),
    markNotificationRead: vi.fn(),
    markAllNotificationsRead: vi.fn(),
  }
})

const note = (overrides: Partial<AppNotification> = {}): AppNotification => ({
  id: 'note-1',
  kind: 'finding_assigned',
  title: 'Gauge drift',
  finding_id: 'finding-1',
  read: false,
  created_at: '2026-11-16T12:00:00Z',
  status: 'sent',
  ...overrides,
})

const Destination = () => {
  const { search } = useLocation()
  return <h1>{`Findings${search}`}</h1>
}

const renderPage = () => {
  const value: AuthContextValue = {
    user: { email: 'ada@example.com', tenantId: 'tenant-acme', role: 'auditee' },
    signIn: vi.fn(),
    signOut: vi.fn(),
  }
  render(
    <AuthContext.Provider value={value}>
      <MemoryRouter initialEntries={['/notifications']}>
        <Routes>
          <Route path="/notifications" element={<NotificationsPage />} />
          <Route path="/findings" element={<Destination />} />
        </Routes>
      </MemoryRouter>
    </AuthContext.Provider>,
  )
}

describe('NotificationsPage', () => {
  beforeEach(() => {
    vi.mocked(listNotifications).mockReset()
    vi.mocked(markNotificationRead).mockReset()
    vi.mocked(markAllNotificationsRead).mockReset()
    vi.mocked(markNotificationRead).mockResolvedValue({ id: 'note-1', read: true })
    vi.mocked(markAllNotificationsRead).mockResolvedValue({ updated: 2 })
  })

  it('lists the history and marks one notification read', async () => {
    vi.mocked(listNotifications).mockResolvedValue({
      items: [
        note(),
        note({ id: 'note-2', title: 'Overdue action', finding_id: 'finding-2', read: true }),
      ],
      unread_count: 1,
    })
    renderPage()

    expect(await screen.findByRole('button', { name: 'Gauge drift' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Overdue action' })).toBeInTheDocument()
    expect(listNotifications).toHaveBeenCalledWith(100)

    await userEvent.click(screen.getByRole('button', { name: 'Mark as read' }))

    expect(markNotificationRead).toHaveBeenCalledWith('note-1')
    expect(screen.queryByRole('button', { name: 'Mark as read' })).not.toBeInTheDocument()
  })

  it('marks every notification read', async () => {
    vi.mocked(listNotifications).mockResolvedValue({
      items: [note(), note({ id: 'note-2', title: 'Overdue action' })],
      unread_count: 2,
    })
    renderPage()

    await screen.findByRole('button', { name: 'Gauge drift' })
    await userEvent.click(screen.getByRole('button', { name: 'Mark all as read' }))

    expect(markAllNotificationsRead).toHaveBeenCalledOnce()
    expect(screen.queryByRole('button', { name: 'Mark as read' })).not.toBeInTheDocument()
  })

  it('opens the related finding from a notification', async () => {
    vi.mocked(listNotifications).mockResolvedValue({
      items: [note()],
      unread_count: 1,
    })
    renderPage()

    await userEvent.click(await screen.findByRole('button', { name: 'Gauge drift' }))

    expect(markNotificationRead).toHaveBeenCalledWith('note-1')
    expect(
      await screen.findByRole('heading', { name: 'Findings?finding=finding-1' }),
    ).toBeInTheDocument()
  })
})
