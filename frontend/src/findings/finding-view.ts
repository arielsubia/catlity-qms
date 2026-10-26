import type { Finding } from '../api/findings-api'

export const FINDING_TYPES = [
  'major_nc',
  'minor_nc',
  'observation',
  'improvement_opportunity',
] as const

export const FINDING_STATUSES = ['open', 'in_progress', 'resolved', 'verified', 'closed'] as const

export type FindingType = (typeof FINDING_TYPES)[number]
export type FindingStatus = (typeof FINDING_STATUSES)[number]
export type ResponsibleFilter = 'all' | 'unassigned'

const TYPE_LABEL: Record<FindingType, string> = {
  major_nc: 'Major',
  minor_nc: 'Minor',
  observation: 'Observation',
  improvement_opportunity: 'Improvement opportunity',
}

const TYPE_COLOR: Record<FindingType, string> = {
  major_nc: 'red',
  minor_nc: 'orange',
  observation: 'blue',
  improvement_opportunity: 'green',
}

const STATUS_LABEL: Record<FindingStatus, string> = {
  open: 'Open',
  in_progress: 'In progress',
  resolved: 'Resolved',
  verified: 'Verified',
  closed: 'Closed',
}

const VERIFIER_ROLES = new Set(['auditor', 'lead_auditor', 'admin'])

export interface FindingStatusAction {
  status: FindingStatus
  label: string
}

export interface AuditTitle {
  id: string
  title: string
}

export const isFindingType = (value: string): value is FindingType =>
  (FINDING_TYPES as readonly string[]).includes(value)

export const isFindingStatus = (value: string): value is FindingStatus =>
  (FINDING_STATUSES as readonly string[]).includes(value)

export const typeLabel = (findingType: string): string =>
  isFindingType(findingType) ? TYPE_LABEL[findingType] : findingType

export const typeColor = (findingType: string): string | undefined =>
  isFindingType(findingType) ? TYPE_COLOR[findingType] : undefined

export const statusLabel = (status: string): string =>
  isFindingStatus(status) ? STATUS_LABEL[status] : status

export const assigneeLabel = (assigneeId: string | null): string => assigneeId ?? 'Unassigned'

export const auditLabel = (auditId: string, audits: AuditTitle[] | null): string =>
  audits?.find((audit) => audit.id === auditId)?.title ?? auditId

// GET /findings has no assignee query. This narrows the page already returned.
export const filterByResponsible = (
  findings: Finding[],
  responsible: ResponsibleFilter,
): Finding[] => {
  if (responsible !== 'unassigned') {
    return findings
  }
  return findings.filter((finding) => finding.assignee_id === null)
}

// The assigned auditee may advance a finding in the API. The session has no
// user id, and no endpoint stores assignee_id, so only admin sees those steps.
export const statusActions = (role: string, status: string): FindingStatusAction[] => {
  const actions: FindingStatusAction[] = []
  if (role === 'admin' && status === 'open') {
    actions.push({ status: 'in_progress', label: 'Move to in progress' })
  }
  if (role === 'admin' && status === 'in_progress') {
    actions.push({ status: 'resolved', label: 'Move to resolved' })
  }
  if (VERIFIER_ROLES.has(role) && status === 'resolved') {
    actions.push({ status: 'verified', label: 'Move to verified' })
    actions.push({ status: 'in_progress', label: 'Return to in progress' })
  }
  if (VERIFIER_ROLES.has(role) && status === 'verified') {
    actions.push({ status: 'closed', label: 'Move to closed' })
  }
  return actions
}
