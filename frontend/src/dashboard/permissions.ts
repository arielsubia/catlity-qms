const DASHBOARD_ROLES = new Set(['admin', 'qa_manager'])

export const canViewDashboard = (role: string): boolean => DASHBOARD_ROLES.has(role)
