import { createContext } from 'react'

import type { SessionUser } from './auth-service'

export interface AuthContextValue {
  user: SessionUser | null
  signIn: (email: string, password: string) => Promise<void>
  signOut: () => Promise<void>
}

export const AuthContext = createContext<AuthContextValue | null>(null)
