import { fetchAuthSession } from 'aws-amplify/auth'

import { appConfig } from '../config/env'

export class ApiError extends Error {
  readonly status: number

  constructor(message: string, status: number) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

const readErrorMessage = async (response: Response): Promise<string> => {
  const fallback = `Request failed (HTTP ${response.status}).`
  try {
    const body: unknown = await response.json()
    if (typeof body !== 'object' || body === null || !('detail' in body)) {
      return fallback
    }
    const { detail } = body as { detail: unknown }
    if (typeof detail === 'string') {
      return detail
    }
    if (Array.isArray(detail) && typeof detail[0]?.msg === 'string') {
      return detail[0].msg
    }
    return fallback
  } catch {
    return fallback
  }
}

const readIdToken = async (): Promise<string> => {
  const session = await fetchAuthSession()
  const token = session.tokens?.idToken?.toString()
  if (!token) {
    throw new ApiError('Sign in again to continue.', 401)
  }
  return token
}

export const apiRequest = async <T>(path: string, init: RequestInit = {}): Promise<T> => {
  const token = await readIdToken()
  const headers = new Headers(init.headers)
  headers.set('Authorization', `Bearer ${token}`)
  if (init.body !== undefined && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }

  let response: Response
  try {
    response = await fetch(`${appConfig.apiBaseUrl}${path}`, { ...init, headers })
  } catch {
    throw new ApiError('Could not reach the API. Check that the backend is running.', 0)
  }

  if (!response.ok) {
    throw new ApiError(await readErrorMessage(response), response.status)
  }

  return (await response.json()) as T
}
