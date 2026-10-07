import { fetchAuthSession, signIn } from 'aws-amplify/auth'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { AuthServiceError, signInWithEmail } from './auth-service'

vi.mock('aws-amplify/auth', () => ({
  fetchAuthSession: vi.fn(),
  signIn: vi.fn(),
  signOut: vi.fn(),
}))

vi.mock('../config/env', () => ({
  isAuthConfigured: () => true,
}))

const namedError = (name: string): Error => Object.assign(new Error(name), { name })

describe('signInWithEmail', () => {
  beforeEach(() => {
    vi.mocked(signIn).mockReset()
    vi.mocked(fetchAuthSession).mockReset()
  })

  it('returns the user claims from the ID token', async () => {
    vi.mocked(signIn).mockResolvedValue({
      isSignedIn: true,
      nextStep: { signInStep: 'DONE' },
    })
    vi.mocked(fetchAuthSession).mockResolvedValue({
      tokens: {
        accessToken: { payload: {} },
        idToken: {
          payload: {
            email: 'ana@acme.com',
            'custom:tenant_id': 'tenant-a',
            'custom:role': 'auditor',
          },
        },
      },
    })

    await expect(signInWithEmail('ana@acme.com', 'secret')).resolves.toEqual({
      email: 'ana@acme.com',
      tenantId: 'tenant-a',
      role: 'auditor',
    })
  })

  it('maps invalid credentials to a friendly message', async () => {
    vi.mocked(signIn).mockRejectedValue(namedError('NotAuthorizedException'))

    await expect(signInWithEmail('ana@acme.com', 'wrong')).rejects.toThrow(
      new AuthServiceError('Incorrect email or password.'),
    )
  })

  it('reports unverified accounts', async () => {
    vi.mocked(signIn).mockResolvedValue({
      isSignedIn: false,
      nextStep: { signInStep: 'CONFIRM_SIGN_UP' },
    })

    await expect(signInWithEmail('ana@acme.com', 'secret')).rejects.toThrow(
      'Your email address has not been verified yet.',
    )
  })
})
