import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { AuthContext, type AuthContextValue } from '../auth/auth-context'
import { AuthServiceError } from '../auth/auth-service'
import { LoginPage } from './login-page'

vi.mock('../config/env', () => ({
  isAuthConfigured: () => true,
}))

const renderLogin = (signIn: AuthContextValue['signIn']) => {
  const value: AuthContextValue = { user: null, signIn, signOut: vi.fn() }
  render(
    <AuthContext.Provider value={value}>
      <LoginPage onSwitchToRegister={vi.fn()} />
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
})
