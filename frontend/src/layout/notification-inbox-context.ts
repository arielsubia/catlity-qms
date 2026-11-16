import { createContext } from 'react'

export interface NotificationInboxContextValue {
  revision: number
  refresh: () => void
}

export const NotificationInboxContext = createContext<NotificationInboxContextValue | null>(null)
