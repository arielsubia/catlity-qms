import { apiRequest } from './http'

export interface Audit {
  id: string
  tenant_id: string
  title: string
  description: string | null
  audit_type: string
  status: string
  status_changed_at: string | null
  planned_date: string | null
  completion_date: string | null
  auditor_id: string | null
  created_at: string
  updated_at: string
}

export interface AuditListResponse {
  items: Audit[]
  total: number
  skip: number
  limit: number
}

export interface AuditListQuery {
  skip: number
  limit: number
  status?: string
}

export interface AuditDraft {
  title: string
  description: string | null
  auditType: string
  plannedDate: string | null
}

export interface AvailableAuditor {
  id: string
  full_name: string
  email: string
  role: string
}

const toPayload = (draft: AuditDraft) => ({
  title: draft.title,
  description: draft.description,
  audit_type: draft.auditType,
  planned_date: draft.plannedDate,
})

export const listAudits = (query: AuditListQuery): Promise<AuditListResponse> => {
  const params = new URLSearchParams({
    skip: String(query.skip),
    limit: String(query.limit),
  })
  if (query.status) {
    params.set('status', query.status)
  }
  return apiRequest<AuditListResponse>(`/api/v1/audits/?${params.toString()}`)
}

export const getAudit = (auditId: string): Promise<Audit> =>
  apiRequest<Audit>(`/api/v1/audits/${auditId}`)

export const createAudit = (draft: AuditDraft): Promise<Audit> =>
  apiRequest<Audit>('/api/v1/audits/', {
    method: 'POST',
    body: JSON.stringify(toPayload(draft)),
  })

export const updateAudit = (auditId: string, draft: AuditDraft): Promise<Audit> =>
  apiRequest<Audit>(`/api/v1/audits/${auditId}`, {
    method: 'PATCH',
    body: JSON.stringify(toPayload(draft)),
  })

export const assignAuditor = (auditId: string, auditorId: string): Promise<Audit> =>
  apiRequest<Audit>(`/api/v1/audits/${auditId}/auditor`, {
    method: 'PATCH',
    body: JSON.stringify({ auditor_id: auditorId }),
  })

export const updateAuditStatus = (auditId: string, status: string): Promise<Audit> =>
  apiRequest<Audit>(`/api/v1/audits/${auditId}/status`, {
    method: 'PATCH',
    body: JSON.stringify({ status }),
  })

export const listAuditors = (): Promise<AvailableAuditor[]> =>
  apiRequest<AvailableAuditor[]>('/api/v1/auditors/')
