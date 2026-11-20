import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter, Route, Routes } from 'react-router-dom'

import { ApiError } from '../api/http'
import {
  sendOnboardingMessage,
  startOnboarding,
  type OnboardingSession,
} from '../api/onboarding-api'
import { AuthContext, type AuthContextValue } from '../auth/auth-context'
import { LoginPage } from './login-page'
import { OnboardingPage } from './onboarding-page'

vi.mock('../api/onboarding-api', async () => {
  const actual =
    await vi.importActual<typeof import('../api/onboarding-api')>('../api/onboarding-api')
  return {
    ...actual,
    startOnboarding: vi.fn(),
    sendOnboardingMessage: vi.fn(),
  }
})

vi.mock('../config/env', () => ({
  isAuthConfigured: () => true,
}))

const opened: OnboardingSession = {
  session_id: 'session-1',
  reply: 'Send the organization name and the industry, separated by a comma.',
  industry_selected: false,
  kb_assigned: false,
  checklists_created: false,
  admin_created: false,
  knowledge_base_ids: null,
  tenant_id: null,
}

const stepItem = (title: string) => screen.getByText(title).closest('.ant-steps-item')

const renderPage = () => {
  const value: AuthContextValue = {
    user: null,
    signIn: vi.fn(),
    signOut: vi.fn(),
  }
  render(
    <AuthContext.Provider value={value}>
      <MemoryRouter initialEntries={['/onboarding']}>
        <Routes>
          <Route path="/onboarding" element={<OnboardingPage />} />
          <Route path="/login" element={<LoginPage />} />
        </Routes>
      </MemoryRouter>
    </AuthContext.Provider>,
  )
  return userEvent.setup()
}

describe('OnboardingPage', () => {
  beforeEach(() => {
    vi.mocked(startOnboarding).mockReset()
    vi.mocked(sendOnboardingMessage).mockReset()
    vi.mocked(startOnboarding).mockResolvedValue(opened)
  })

  it('shows the assistant prompt and four pending steps', async () => {
    renderPage()

    expect(
      await screen.findByText('Send the organization name and the industry, separated by a comma.'),
    ).toBeInTheDocument()
    expect(screen.getByText('Onboarding Assistant')).toBeInTheDocument()
    expect(stepItem('Organization')).toHaveClass('ant-steps-item-process')
    expect(stepItem('Knowledge base')).toHaveClass('ant-steps-item-wait')
    expect(stepItem('Checklist')).toHaveClass('ant-steps-item-wait')
    expect(stepItem('Administrator')).toHaveClass('ant-steps-item-wait')
    expect(startOnboarding).toHaveBeenCalledTimes(1)
  })

  it('marks the first three steps after the organization message', async () => {
    vi.mocked(sendOnboardingMessage).mockResolvedValue({
      ...opened,
      reply: 'Send the administrator full name and email, separated by a comma.',
      industry_selected: true,
      kb_assigned: true,
      checklists_created: true,
    })
    const user = renderPage()
    await screen.findByText('Send the organization name and the industry, separated by a comma.')

    await user.type(screen.getByRole('textbox', { name: 'Message' }), 'North Plant, automotive')
    await user.click(screen.getByRole('button', { name: 'Send' }))

    expect(await screen.findByText('You')).toBeInTheDocument()
    expect(screen.getByText('North Plant, automotive')).toBeInTheDocument()
    expect(
      await screen.findByText('Send the administrator full name and email, separated by a comma.'),
    ).toBeInTheDocument()
    expect(sendOnboardingMessage).toHaveBeenCalledWith('session-1', 'North Plant, automotive')
    expect(stepItem('Organization')).toHaveClass('ant-steps-item-finish')
    expect(stepItem('Knowledge base')).toHaveClass('ant-steps-item-finish')
    expect(stepItem('Checklist')).toHaveClass('ant-steps-item-finish')
    expect(stepItem('Administrator')).toHaveClass('ant-steps-item-process')
  })

  it('opens sign-in with the created administrator', async () => {
    vi.mocked(sendOnboardingMessage)
      .mockResolvedValueOnce({
        ...opened,
        reply: 'Send the administrator full name and email, separated by a comma.',
        industry_selected: true,
        kb_assigned: true,
        checklists_created: true,
      })
      .mockResolvedValueOnce({
        ...opened,
        reply:
          'North Plant is active in automotive. Knowledge bases: common OTQJ8TMBNI. Administrator: Ada Lovelace <ada@north.example>.',
        industry_selected: true,
        kb_assigned: true,
        checklists_created: true,
        admin_created: true,
        tenant_id: 'tenant-1',
      })
    const user = renderPage()
    await screen.findByText('Send the organization name and the industry, separated by a comma.')
    await user.type(screen.getByRole('textbox', { name: 'Message' }), 'North Plant, automotive')
    await user.click(screen.getByRole('button', { name: 'Send' }))
    await screen.findByText('Send the administrator full name and email, separated by a comma.')

    await user.type(
      screen.getByRole('textbox', { name: 'Message' }),
      'Ada Lovelace, ada@north.example',
    )
    await user.click(screen.getByRole('button', { name: 'Send' }))

    expect(await screen.findByText('Sign in to Catlity QMS')).toBeInTheDocument()
    expect(
      screen.getByText(
        'Your organization is registered. Ada Lovelace (ada@north.example) cannot sign in yet: this account has no password.',
      ),
    ).toBeInTheDocument()
    expect(screen.getByLabelText('Email')).toHaveValue('ada@north.example')
  })

  it('shows the API error and keeps the conversation', async () => {
    vi.mocked(sendOnboardingMessage).mockRejectedValue(
      new ApiError('A user with this email already exists', 409),
    )
    const user = renderPage()
    await screen.findByText('Send the organization name and the industry, separated by a comma.')
    await user.type(
      screen.getByRole('textbox', { name: 'Message' }),
      'Ada Lovelace, ada@north.example',
    )
    await user.click(screen.getByRole('button', { name: 'Send' }))

    expect(await screen.findByText('A user with this email already exists')).toBeInTheDocument()
    expect(screen.getByText('Ada Lovelace, ada@north.example')).toBeInTheDocument()
    expect(screen.queryByText('Sign in to Catlity QMS')).not.toBeInTheDocument()
  })
})
