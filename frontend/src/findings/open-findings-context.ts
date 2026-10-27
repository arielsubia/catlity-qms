import { createContext } from 'react'

export interface OpenFindingsHandle {
  refresh: () => void
}

export const OpenFindingsContext = createContext<OpenFindingsHandle | null>(null)
