import type { Audit, AvailableAuditor } from '../api/audits-api'

export const AUDIT_STATUSES = ['planned', 'in_progress', 'completed', 'closed'] as const

export type AuditStatus = (typeof AUDIT_STATUSES)[number]

const STATUS_LABEL: Record<AuditStatus, string> = {
  planned: 'Planned',
  in_progress: 'In progress',
  completed: 'Completed',
  closed: 'Closed',
}

export const isAuditStatus = (value: string): value is AuditStatus =>
  (AUDIT_STATUSES as readonly string[]).includes(value)

export const statusLabel = (status: string): string =>
  isAuditStatus(status) ? STATUS_LABEL[status] : status

export const nextStatus = (status: string): AuditStatus | null => {
  if (!isAuditStatus(status)) {
    return null
  }
  const index = AUDIT_STATUSES.indexOf(status)
  return AUDIT_STATUSES[index + 1] ?? null
}

export const auditorLabel = (
  auditorId: string | null,
  auditors: AvailableAuditor[] | null,
): string => {
  if (!auditorId) {
    return 'Unassigned'
  }
  const match = auditors?.find((auditor) => auditor.id === auditorId)
  return match?.full_name ?? auditorId
}

// The list endpoint filters by status. A date range only narrows the page already returned.
export const filterByPlannedDate = (audits: Audit[], from: string, to: string): Audit[] => {
  if (!from && !to) {
    return audits
  }
  return audits.filter((audit) => {
    if (!audit.planned_date) {
      return false
    }
    if (from && audit.planned_date < from) {
      return false
    }
    if (to && audit.planned_date > to) {
      return false
    }
    return true
  })
}

export const formatStatusChangedAt = (value: string): string => {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return value
  }
  const pad = (part: number) => String(part).padStart(2, '0')
  const day = `${date.getUTCFullYear()}-${pad(date.getUTCMonth() + 1)}-${pad(date.getUTCDate())}`
  const time = `${pad(date.getUTCHours())}:${pad(date.getUTCMinutes())}`
  return `${day} ${time} UTC`
}
