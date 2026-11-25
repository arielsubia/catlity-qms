import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryRouter, RouterProvider } from 'react-router-dom'

import { listFindings } from '../api/findings-api'
import { AuthContext, type AuthContextValue } from '../auth/auth-context'
import type { SessionUser } from '../auth/auth-service'
import { SectionPage } from '../pages/section-page'
import { AppLayout } from './app-layout'
import { NAV_ITEMS } from './nav-items'

vi.mock('../api/findings-api', () => ({
  listFindings: vi.fn().mockResolvedValue({ items: [], total: 4, skip: 0, limit: 1 }),
}))

vi.mock('../api/notifications-api', () => ({
  listNotifications: vi.fn().mockResolvedValue({ items: [], unread_count: 0 }),
  markNotificationRead: vi.fn(),
  markAllNotificationsRead: vi.fn(),
  findingPath: (findingId: string | null) =>
    findingId ? `/findings?finding=${findingId}` : '/findings',
}))

const user: SessionUser = {
  email: 'ana@acme.com',
  tenantId: 'tenant-acme',
  role: 'auditor',
}

const installMatchMedia = (matches: (query: string) => boolean) => {
  Object.defineProperty(window, 'matchMedia', {
    writable: true,
    value: vi.fn((query: string) => ({
      matches: matches(query),
      media: query,
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })),
  })
}

const renderLayout = async (
  signOut: AuthContextValue['signOut'] = vi.fn(),
  path = '/dashboard',
  role = 'auditor',
) => {
  const value: AuthContextValue = { user: { ...user, role }, signIn: vi.fn(), signOut }
  const router = createMemoryRouter(
    [
      {
        element: <AppLayout />,
        children: NAV_ITEMS.map((item) => ({
          path: item.path.slice(1),
          element: <SectionPage />,
        })),
      },
      { path: 'login', element: <h1>Sign in</h1> },
    ],
    { initialEntries: [path] },
  )
  render(
    <AuthContext.Provider value={value}>
      <RouterProvider router={router} />
    </AuthContext.Provider>,
  )
  await waitFor(() => {
    expect(screen.getByRole('menuitem', { name: /Findings/ })).toHaveTextContent('4')
  })
  return router
}

describe('AppLayout', () => {
  beforeEach(() => {
    vi.mocked(listFindings).mockClear()
  })

  afterEach(() => {
    installMatchMedia(() => false)
  })

  it('lists the main sections and the open findings total', async () => {
    await renderLayout()

    expect(screen.queryByRole('menuitem', { name: 'Dashboard' })).not.toBeInTheDocument()
    for (const item of NAV_ITEMS.filter((entry) => entry.path !== '/dashboard')) {
      const name = item.path === '/findings' ? /Findings/ : item.label
      expect(screen.getByRole('menuitem', { name })).toBeInTheDocument()
      expect(screen.getByRole('link', { name })).toHaveAttribute('href', item.path)
    }
    expect(listFindings).toHaveBeenCalledWith({ skip: 0, limit: 1, status: 'open' })
  })

  it.each(['admin', 'qa_manager'])('shows Dashboard for %s', async (role) => {
    await renderLayout(vi.fn(), '/audits', role)

    expect(screen.getByRole('menuitem', { name: 'Dashboard' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Dashboard' })).toHaveAttribute('href', '/dashboard')
  })

  it('shows the signed-in user in the header', async () => {
    await renderLayout()

    expect(screen.getByText('ana@acme.com')).toBeInTheDocument()
    expect(screen.getByText('auditor')).toBeInTheDocument()
    expect(screen.getByText('tenant-acme')).toBeInTheDocument()
    expect(screen.getByText('Organization')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Notifications' })).toBeInTheDocument()
  })

  it('signs the user out from the header', async () => {
    const signOut = vi.fn()
    const router = await renderLayout(signOut)

    await userEvent.click(screen.getByRole('button', { name: 'Sign out' }))

    expect(signOut).toHaveBeenCalledOnce()
    expect(router.state.location.pathname).toBe('/login')
  })

  it('switches the content title from the sidebar', async () => {
    const router = await renderLayout()

    expect(screen.getByRole('heading', { level: 2, name: 'Dashboard' })).toBeInTheDocument()

    await userEvent.click(screen.getByRole('menuitem', { name: /Findings/ }))

    expect(screen.getByRole('heading', { level: 2, name: 'Findings' })).toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/findings')
  })

  it('opens the menu from the header on a narrow viewport', async () => {
    installMatchMedia((query) => query.includes('max-width'))
    await renderLayout()

    await userEvent.click(await screen.findByRole('button', { name: 'Open menu' }))

    expect(screen.getByRole('button', { name: 'Close menu' })).toBeInTheDocument()
  })
})
