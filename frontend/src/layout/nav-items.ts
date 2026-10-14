export const NAV_ITEMS = [
  { key: 'dashboard', label: 'Dashboard' },
  { key: 'audits', label: 'Audits' },
  { key: 'findings', label: 'Findings' },
  { key: 'evidence', label: 'Evidence' },
  { key: 'ai-agent', label: 'AI Agent' },
  { key: 'settings', label: 'Settings' },
] as const

export type SectionKey = (typeof NAV_ITEMS)[number]['key']
