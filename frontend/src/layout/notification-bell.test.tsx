import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { createMemoryRouter, RouterProvider, useLocation } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import {
  listNotifications,
  markAllNotificationsRead,
  markNotificationRead,
  type AppNotification,
} from '../api/notifications-api'
import { NotificationBell } from './notification-bell'
import { NotificationInboxContext } from './notification-inbox-context'

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

const LocationProbe = () => {
  const location = useLocation()
  return <h1>{`${location.pathname}${location.search}`}</h1>
}

const renderBell = () => {
  const router = createMemoryRouter(
    [
      {
        element: (
          <NotificationInboxContext.Provider value={{ revision: 0, refresh: vi.fn() }}>
            <NotificationBell />
            <LocationProbe />
          </NotificationInboxContext.Provider>
        ),
        children: [
          { path: '/', element: null },
          { path: '/findings', element: null },
          { path: '/notifications', element: null },
        ],
      },
    ],
    { initialEntries: ['/'] },
  )
  render(<RouterProvider router={router} />)
  return router
}

describe('NotificationBell', () => {
  beforeEach(() => {
    vi.mocked(listNotifications).mockReset()
    vi.mocked(markNotificationRead).mockReset()
    vi.mocked(markAllNotificationsRead).mockReset()
    vi.mocked(markNotificationRead).mockResolvedValue({ id: 'note-1', read: true })
    vi.mocked(markAllNotificationsRead).mockResolvedValue({ updated: 1 })
  })

  it('shows the unread count and the latest five notifications', async () => {
    vi.mocked(listNotifications).mockResolvedValue({
      items: [
        note({ id: 'note-1', title: 'One' }),
        note({ id: 'note-2', title: 'Two' }),
        note({ id: 'note-3', title: 'Three' }),
        note({ id: 'note-4', title: 'Four' }),
        note({ id: 'note-5', title: 'Five' }),
      ],
      unread_count: 6,
    })
    renderBell()

    expect(await screen.findByText('6')).toBeInTheDocument()
    expect(listNotifications).toHaveBeenCalledWith(5)

    await userEvent.click(screen.getByRole('button', { name: 'Notifications' }))

    for (const title of ['One', 'Two', 'Three', 'Four', 'Five']) {
      expect(screen.getByRole('button', { name: title })).toBeInTheDocument()
    }
  })

  it('marks one notification read and opens the related finding', async () => {
    vi.mocked(listNotifications).mockResolvedValue({
      items: [note()],
      unread_count: 1,
    })
    renderBell()

    await userEvent.click(await screen.findByRole('button', { name: 'Notifications' }))
    await userEvent.click(screen.getByRole('button', { name: 'Gauge drift' }))

    expect(markNotificationRead).toHaveBeenCalledWith('note-1')
    expect(
      await screen.findByRole('heading', { name: '/findings?finding=finding-1' }),
    ).toBeInTheDocument()
  })

  it('marks every notification read from the dropdown', async () => {
    vi.mocked(listNotifications).mockResolvedValue({
      items: [note()],
      unread_count: 1,
    })
    renderBell()

    await userEvent.click(await screen.findByRole('button', { name: 'Notifications' }))
    await userEvent.click(screen.getByRole('button', { name: 'Mark all as read' }))

    expect(markAllNotificationsRead).toHaveBeenCalledOnce()
  })
})
