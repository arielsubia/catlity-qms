import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter, Route, Routes } from 'react-router-dom'

import { RegisterError, registerUser } from '../api/auth-api'
import { RegisterPage } from './register-page'

vi.mock('../api/auth-api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../api/auth-api')>()
  return { ...actual, registerUser: vi.fn() }
})

const renderRegister = () => {
  render(
    <MemoryRouter initialEntries={['/register']}>
      <Routes>
        <Route path="/register" element={<RegisterPage />} />
        <Route path="/login" element={<h1>Sign in to Catlity QMS</h1>} />
      </Routes>
    </MemoryRouter>,
  )
}

const fillForm = async (password: string) => {
  await userEvent.type(screen.getByLabelText('Full name'), 'Ana Perez')
  await userEvent.type(screen.getByLabelText('Email'), 'ana@acme.com')
  await userEvent.type(screen.getByLabelText('Password'), password)
  await userEvent.type(screen.getByLabelText('Organization ID'), 'tenant-a')
  await userEvent.click(screen.getByRole('button', { name: 'Create account' }))
}

describe('RegisterPage', () => {
  beforeEach(() => {
    vi.mocked(registerUser).mockReset()
  })

  it('rejects passwords shorter than 12 characters', async () => {
    renderRegister()

    await fillForm('short')

    expect(
      await screen.findByText('The password must have at least 12 characters.'),
    ).toBeInTheDocument()
    expect(registerUser).not.toHaveBeenCalled()
  })

  it('sends the form data without a role and confirms the account', async () => {
    vi.mocked(registerUser).mockResolvedValue()
    renderRegister()

    await fillForm('SuperSecret123!')

    expect(await screen.findByText('You can sign in now.')).toBeInTheDocument()
    expect(registerUser).toHaveBeenCalledWith({
      fullName: 'Ana Perez',
      email: 'ana@acme.com',
      password: 'SuperSecret123!',
      tenantId: 'tenant-a',
    })
  })

  it('shows the error returned by the API', async () => {
    vi.mocked(registerUser).mockRejectedValue(new RegisterError('Tenant not found'))
    renderRegister()

    await fillForm('SuperSecret123!')

    expect(await screen.findByText('Tenant not found')).toBeInTheDocument()
  })

  it('returns to sign in from the form', async () => {
    renderRegister()

    await userEvent.click(screen.getByRole('button', { name: 'Sign in' }))

    expect(screen.getByRole('heading', { name: 'Sign in to Catlity QMS' })).toBeInTheDocument()
  })

  it('returns to sign in from the confirmation', async () => {
    vi.mocked(registerUser).mockResolvedValue()
    renderRegister()

    await fillForm('SuperSecret123!')
    await userEvent.click(await screen.findByRole('button', { name: 'Go to sign in' }))

    expect(screen.getByRole('heading', { name: 'Sign in to Catlity QMS' })).toBeInTheDocument()
  })
})
