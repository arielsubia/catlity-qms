const EDITOR_ROLES = new Set(['auditor', 'admin', 'lead_auditor'])

export const canCreateFinding = (role: string): boolean => EDITOR_ROLES.has(role)

export const canEditFinding = (role: string): boolean => EDITOR_ROLES.has(role)
