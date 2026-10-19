import { Navigate, Outlet } from 'react-router-dom'

import { useAuth } from '../auth/use-auth'

export const RequireAuth = () => {
  const { user } = useAuth()
  if (!user) {
    return <Navigate to="/login" replace />
  }
  return <Outlet />
}

export const GuestOnly = () => {
  const { user } = useAuth()
  if (user) {
    return <Navigate to="/dashboard" replace />
  }
  return <Outlet />
}

export const SessionRedirect = () => {
  const { user } = useAuth()
  return <Navigate to={user ? '/dashboard' : '/login'} replace />
}
