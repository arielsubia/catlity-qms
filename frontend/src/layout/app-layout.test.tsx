import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { createMemoryRouter, RouterProvider } from 'react-router-dom'

import { AuthContext, type AuthContextValue } from '../auth/auth-context'
import type { SessionUser } from '../auth/auth-service'
import { SectionPage } from '../pages/section-page'
import { AppLayout } from './app-layout'
import { NAV_ITEMS } from './nav-items'

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

const renderLayout = (signOut: AuthContextValue['signOut'] = vi.fn(), path = '/dashboard') => {
  const value: AuthContextValue = { user, signIn: vi.fn(), signOut }
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
  return router
}

describe('AppLayout', () => {
  afterEach(() => {
    installMatchMedia(() => false)
  })

  it('lists the main sections', () => {
    renderLayout()

    for (const item of NAV_ITEMS) {
      expect(screen.getByRole('menuitem', { name: item.label })).toBeInTheDocument()
      expect(screen.getByRole('link', { name: item.label })).toHaveAttribute('href', item.path)
    }
  })

  it('shows the signed-in user in the header', () => {
    renderLayout()

    expect(screen.getByText('ana@acme.com')).toBeInTheDocument()
    expect(screen.getByText('auditor')).toBeInTheDocument()
    expect(screen.getByText('tenant-acme')).toBeInTheDocument()
    expect(screen.getByText('Organization')).toBeInTheDocument()
  })

  it('signs the user out from the header', async () => {
    const signOut = vi.fn()
    const router = renderLayout(signOut)

    await userEvent.click(screen.getByRole('button', { name: 'Sign out' }))

    expect(signOut).toHaveBeenCalledOnce()
    expect(router.state.location.pathname).toBe('/login')
  })

  it('switches the content title from the sidebar', async () => {
    const router = renderLayout()

    expect(screen.getByRole('heading', { level: 2, name: 'Dashboard' })).toBeInTheDocument()

    await userEvent.click(screen.getByRole('menuitem', { name: 'Findings' }))

    expect(screen.getByRole('heading', { level: 2, name: 'Findings' })).toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/findings')
  })

  it('opens the menu from the header on a narrow viewport', async () => {
    installMatchMedia((query) => query.includes('max-width'))
    renderLayout()

    await userEvent.click(await screen.findByRole('button', { name: 'Open menu' }))

    expect(screen.getByRole('button', { name: 'Close menu' })).toBeInTheDocument()
  })
})
