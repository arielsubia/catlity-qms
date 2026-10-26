import { apiRequest } from './http'

export interface Finding {
  id: string
  tenant_id: string
  audit_id: string
  title: string
  description: string | null
  finding_type: string
  severity: string
  status: string
  status_changed_at: string | null
  clause_reference: string | null
  assignee_id: string | null
  created_at: string
  updated_at: string
}

export interface FindingListResponse {
  items: Finding[]
  total: number
  skip: number
  limit: number
}

export interface FindingListQuery {
  skip: number
  limit: number
  findingType?: string
  status?: string
}

export interface FindingDraft {
  title: string
  description: string | null
  findingType: string
  severity: string
  clauseReference: string | null
}

const toPayload = (draft: FindingDraft) => ({
  title: draft.title,
  description: draft.description,
  finding_type: draft.findingType,
  severity: draft.severity,
  clause_reference: draft.clauseReference,
})

export const listFindings = (query: FindingListQuery): Promise<FindingListResponse> => {
  const params = new URLSearchParams({
    skip: String(query.skip),
    limit: String(query.limit),
  })
  if (query.findingType) {
    params.set('finding_type', query.findingType)
  }
  if (query.status) {
    params.set('status', query.status)
  }
  return apiRequest<FindingListResponse>(`/api/v1/findings?${params.toString()}`)
}

export const createFinding = (auditId: string, draft: FindingDraft): Promise<Finding> =>
  apiRequest<Finding>(`/api/v1/audits/${auditId}/findings`, {
    method: 'POST',
    body: JSON.stringify(toPayload(draft)),
  })

export const updateFinding = (findingId: string, draft: FindingDraft): Promise<Finding> =>
  apiRequest<Finding>(`/api/v1/findings/${findingId}`, {
    method: 'PATCH',
    body: JSON.stringify(toPayload(draft)),
  })

export const updateFindingStatus = (findingId: string, status: string): Promise<Finding> =>
  apiRequest<Finding>(`/api/v1/findings/${findingId}/status`, {
    method: 'PATCH',
    body: JSON.stringify({ status }),
  })
