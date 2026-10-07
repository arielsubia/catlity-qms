import { appConfig } from '../config/env'

export interface RegisterInput {
  email: string
  password: string
  fullName: string
  tenantId: string
}

export class RegisterError extends Error {}

const extractErrorDetail = async (response: Response): Promise<string> => {
  const fallback = `Registration failed (HTTP ${response.status}).`
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

// The role is intentionally not sent: tenant and role assignment must stay server-side.
export const registerUser = async (input: RegisterInput): Promise<void> => {
  let response: Response
  try {
    response = await fetch(`${appConfig.apiBaseUrl}/api/v1/auth/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        email: input.email,
        password: input.password,
        full_name: input.fullName,
        tenant_id: input.tenantId,
      }),
    })
  } catch {
    throw new RegisterError('Could not reach the API. Check that the backend is running.')
  }

  if (!response.ok) {
    throw new RegisterError(await extractErrorDetail(response))
  }
}
