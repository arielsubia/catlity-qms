import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { AuthContext, type AuthContextValue } from '../auth/auth-context'
import type { SessionUser } from '../auth/auth-service'
import { AppLayout } from './app-layout'

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

const renderLayout = (signOut: AuthContextValue['signOut'] = vi.fn()) => {
  const value: AuthContextValue = { user, signIn: vi.fn(), signOut }
  render(
    <AuthContext.Provider value={value}>
      <AppLayout />
    </AuthContext.Provider>,
  )
}

describe('AppLayout', () => {
  afterEach(() => {
    installMatchMedia(() => false)
  })

  it('lists the main sections', () => {
    renderLayout()

    for (const label of ['Dashboard', 'Audits', 'Findings', 'Evidence', 'AI Agent', 'Settings']) {
      expect(screen.getByRole('menuitem', { name: label })).toBeInTheDocument()
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
    renderLayout(signOut)

    await userEvent.click(screen.getByRole('button', { name: 'Sign out' }))

    expect(signOut).toHaveBeenCalledOnce()
  })

  it('switches the content title from the sidebar', async () => {
    renderLayout()

    expect(screen.getByRole('heading', { level: 2, name: 'Dashboard' })).toBeInTheDocument()

    await userEvent.click(screen.getByRole('menuitem', { name: 'Findings' }))

    expect(screen.getByRole('heading', { level: 2, name: 'Findings' })).toBeInTheDocument()
  })

  it('opens the menu from the header on a narrow viewport', async () => {
    installMatchMedia((query) => query.includes('max-width'))
    renderLayout()

    await userEvent.click(await screen.findByRole('button', { name: 'Open menu' }))

    expect(screen.getByRole('button', { name: 'Close menu' })).toBeInTheDocument()
  })
})
