import { fetchAuthSession, signIn, signOut } from 'aws-amplify/auth'

import { isAuthConfigured } from '../config/env'

export interface SessionUser {
  email: string
  tenantId: string
  role: string
}

export class AuthServiceError extends Error {}

const INVALID_CREDENTIALS = 'Incorrect email or password.'

const SIGN_IN_ERROR_MESSAGES: Record<string, string> = {
  NotAuthorizedException: INVALID_CREDENTIALS,
  UserNotFoundException: INVALID_CREDENTIALS,
  UserNotConfirmedException: 'Your email address has not been verified yet.',
  PasswordResetRequiredException: 'You must reset your password before signing in.',
}

const NEXT_STEP_MESSAGES: Record<string, string> = {
  CONFIRM_SIGN_UP: 'Your email address has not been verified yet.',
  RESET_PASSWORD: 'You must reset your password before signing in.',
  CONFIRM_SIGN_IN_WITH_NEW_PASSWORD_REQUIRED: 'You must set a new password before signing in.',
}

const toAuthServiceError = (error: unknown): AuthServiceError => {
  if (error instanceof AuthServiceError) {
    return error
  }
  const name = error instanceof Error ? error.name : ''
  return new AuthServiceError(
    SIGN_IN_ERROR_MESSAGES[name] ?? 'Sign-in failed. Please try again later.',
  )
}

export const getSessionUser = async (): Promise<SessionUser | null> => {
  if (!isAuthConfigured()) {
    return null
  }
  const session = await fetchAuthSession()
  const payload = session.tokens?.idToken?.payload
  if (!payload) {
    return null
  }
  return {
    email: String(payload.email ?? ''),
    tenantId: String(payload['custom:tenant_id'] ?? ''),
    role: String(payload['custom:role'] ?? ''),
  }
}

export const signInWithEmail = async (email: string, password: string): Promise<SessionUser> => {
  if (!isAuthConfigured()) {
    throw new AuthServiceError(
      'Authentication is not configured. Set the Cognito variables in .env.local.',
    )
  }

  try {
    const result = await signIn({ username: email, password })
    if (!result.isSignedIn) {
      throw new AuthServiceError(
        NEXT_STEP_MESSAGES[result.nextStep.signInStep] ??
          'An additional sign-in step is required for this account.',
      )
    }
    const user = await getSessionUser()
    if (!user) {
      throw new AuthServiceError('Signed in, but no session token was returned.')
    }
    return user
  } catch (error) {
    throw toAuthServiceError(error)
  }
}

export const signOutUser = async (): Promise<void> => {
  if (isAuthConfigured()) {
    await signOut()
  }
}
