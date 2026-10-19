import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'

import { AuthContext, type AuthContextValue } from '../auth/auth-context'
import type { SessionUser } from '../auth/auth-service'
import { NAV_ITEMS } from '../layout/nav-items'
import { AppRoutes } from './app-routes'

const signedInUser: SessionUser = {
  email: 'ana@acme.com',
  tenantId: 'tenant-acme',
  role: 'auditor',
}

const renderRoutes = (path: string, user: SessionUser | null) => {
  const value: AuthContextValue = {
    user,
    signIn: async () => undefined,
    signOut: async () => undefined,
  }
  render(
    <AuthContext.Provider value={value}>
      <MemoryRouter initialEntries={[path]}>
        <AppRoutes />
      </MemoryRouter>
    </AuthContext.Provider>,
  )
}

const AuthHarness = ({
  initialPath,
  initialUser,
}: {
  initialPath: string
  initialUser: SessionUser | null
}) => {
  const [user, setUser] = useState(initialUser)
  const value: AuthContextValue = {
    user,
    signIn: async () => {
      setUser(signedInUser)
    },
    signOut: async () => {
      setUser(null)
    },
  }

  return (
    <AuthContext.Provider value={value}>
      <MemoryRouter initialEntries={[initialPath]}>
        <AppRoutes />
      </MemoryRouter>
    </AuthContext.Provider>
  )
}

describe('AppRoutes', () => {
  it.each(NAV_ITEMS.map((item) => item.path))(
    'sends %s to login when there is no session',
    (path) => {
      renderRoutes(path, null)

      expect(screen.getByText('Sign in to Catlity QMS')).toBeInTheDocument()
      expect(screen.queryByText('This section is not available yet.')).not.toBeInTheDocument()
    },
  )

  it.each(NAV_ITEMS.map((item) => [item.path, item.label] as const))(
    'renders the %s placeholder for a signed-in user',
    (path, label) => {
      renderRoutes(path, signedInUser)

      expect(screen.getByRole('heading', { level: 2, name: label })).toBeInTheDocument()
      expect(screen.getByText('This section is not available yet.')).toBeInTheDocument()
    },
  )

  it.each(['/', '/missing'])('sends %s to login without a session', (path) => {
    renderRoutes(path, null)
    expect(screen.getByText('Sign in to Catlity QMS')).toBeInTheDocument()
  })

  it.each(['/', '/missing'])('sends %s to the dashboard with a session', (path) => {
    renderRoutes(path, signedInUser)
    expect(screen.getByRole('heading', { level: 2, name: 'Dashboard' })).toBeInTheDocument()
  })

  it.each(['/login', '/register'])('sends a signed-in user from %s to the dashboard', (path) => {
    renderRoutes(path, signedInUser)
    expect(screen.getByRole('heading', { level: 2, name: 'Dashboard' })).toBeInTheDocument()
  })

  it('opens the dashboard after a successful sign-in', async () => {
    render(<AuthHarness initialPath="/login" initialUser={null} />)

    await userEvent.type(screen.getByLabelText('Email'), 'ana@acme.com')
    await userEvent.type(screen.getByLabelText('Password'), 'SuperSecret123!')
    await userEvent.click(screen.getByRole('button', { name: 'Sign in' }))

    expect(await screen.findByRole('heading', { level: 2, name: 'Dashboard' })).toBeInTheDocument()
  })

  it('returns to login after sign-out', async () => {
    render(<AuthHarness initialPath="/audits" initialUser={signedInUser} />)

    await userEvent.click(screen.getByRole('button', { name: 'Sign out' }))

    expect(await screen.findByText('Sign in to Catlity QMS')).toBeInTheDocument()
    expect(screen.queryByRole('heading', { level: 2, name: 'Audits' })).not.toBeInTheDocument()
  })

  it('moves between login and register by url', async () => {
    renderRoutes('/login', null)

    await userEvent.click(screen.getByRole('button', { name: 'Create one' }))
    expect(screen.getByText('Create your account')).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: 'Sign in' }))
    expect(screen.getByText('Sign in to Catlity QMS')).toBeInTheDocument()
  })
})
