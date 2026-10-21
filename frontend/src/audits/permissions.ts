const CREATOR_ROLES = new Set(['auditor', 'admin', 'lead_auditor'])
const STATUS_ROLES = new Set(['auditor', 'admin'])
const AUDITOR_LIST_ROLES = new Set(['lead_auditor', 'admin'])

export const canCreateAudit = (role: string): boolean => CREATOR_ROLES.has(role)

export const canEditAudit = (role: string): boolean => role !== 'qa_manager'

export const canAssignAuditor = (role: string): boolean => role === 'lead_auditor'

export const canChangeStatus = (role: string): boolean => STATUS_ROLES.has(role)

export const canListAuditors = (role: string): boolean => AUDITOR_LIST_ROLES.has(role)
