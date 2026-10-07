import { useCallback, useMemo, useState, type ReactNode } from 'react'

import { AuthContext, type AuthContextValue } from './auth-context'
import { signInWithEmail, signOutUser, type SessionUser } from './auth-service'

interface AuthProviderProps {
  children: ReactNode
}

export const AuthProvider = ({ children }: AuthProviderProps) => {
  const [user, setUser] = useState<SessionUser | null>(null)

  const signIn = useCallback(async (email: string, password: string) => {
    setUser(await signInWithEmail(email, password))
  }, [])

  const signOut = useCallback(async () => {
    await signOutUser()
    setUser(null)
  }, [])

  const value = useMemo<AuthContextValue>(
    () => ({ user, signIn, signOut }),
    [user, signIn, signOut],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
