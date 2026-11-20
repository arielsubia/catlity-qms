import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { MemoryRouter, Route, Routes } from 'react-router-dom'

import { AuthContext, type AuthContextValue } from '../auth/auth-context'
import { AuthServiceError } from '../auth/auth-service'
import { LoginPage } from './login-page'

vi.mock('../config/env', () => ({
  isAuthConfigured: () => true,
}))

const renderLogin = (
  signIn: AuthContextValue['signIn'],
  state?: { fullName: string; email: string },
) => {
  const value: AuthContextValue = { user: null, signIn, signOut: vi.fn() }
  render(
    <AuthContext.Provider value={value}>
      <MemoryRouter initialEntries={[{ pathname: '/login', state }]}>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<h1>Create your account</h1>} />
          <Route path="/onboarding" element={<h1>Register your organization</h1>} />
          <Route path="/dashboard" element={<h1>Dashboard</h1>} />
        </Routes>
      </MemoryRouter>
    </AuthContext.Provider>,
  )
}

describe('LoginPage', () => {
  it('requires email and password', async () => {
    const signIn = vi.fn()
    renderLogin(signIn)

    await userEvent.click(screen.getByRole('button', { name: 'Sign in' }))

    expect(await screen.findByText('Please enter your email.')).toBeInTheDocument()
    expect(await screen.findByText('Please enter your password.')).toBeInTheDocument()
    expect(signIn).not.toHaveBeenCalled()
  })

  it('shows the error returned by the auth service', async () => {
    const signIn = vi.fn().mockRejectedValue(new AuthServiceError('Incorrect email or password.'))
    renderLogin(signIn)

    await userEvent.type(screen.getByLabelText('Email'), 'ana@acme.com')
    await userEvent.type(screen.getByLabelText('Password'), 'wrong-password')
    await userEvent.click(screen.getByRole('button', { name: 'Sign in' }))

    expect(await screen.findByText('Incorrect email or password.')).toBeInTheDocument()
    expect(signIn).toHaveBeenCalledWith('ana@acme.com', 'wrong-password')
  })

  it('opens the dashboard after a successful sign-in', async () => {
    const signIn = vi.fn().mockResolvedValue(undefined)
    renderLogin(signIn)

    await userEvent.type(screen.getByLabelText('Email'), 'ana@acme.com')
    await userEvent.type(screen.getByLabelText('Password'), 'SuperSecret123!')
    await userEvent.click(screen.getByRole('button', { name: 'Sign in' }))

    expect(await screen.findByRole('heading', { name: 'Dashboard' })).toBeInTheDocument()
    expect(signIn).toHaveBeenCalledWith('ana@acme.com', 'SuperSecret123!')
  })

  it('opens the register page from the sign-in form', async () => {
    renderLogin(vi.fn())

    await userEvent.click(screen.getByRole('button', { name: 'Create one' }))

    expect(screen.getByRole('heading', { name: 'Create your account' })).toBeInTheDocument()
  })

  it('opens organization registration from the sign-in form', async () => {
    renderLogin(vi.fn())

    await userEvent.click(screen.getByRole('button', { name: 'Register your organization' }))

    expect(screen.getByRole('heading', { name: 'Register your organization' })).toBeInTheDocument()
  })

  it('shows the created administrator and fills the email', () => {
    renderLogin(vi.fn(), { fullName: 'Ada Lovelace', email: 'ada@north.example' })

    expect(
      screen.getByText(
        'Your organization is registered. Ada Lovelace (ada@north.example) cannot sign in yet: this account has no password.',
      ),
    ).toBeInTheDocument()
    expect(screen.getByLabelText('Email')).toHaveValue('ada@north.example')
  })
})
