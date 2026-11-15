import { apiRequest } from './http'

export interface ReportReference {
  document: string
  section: string
}

export interface AuditReportDraft {
  id: string
  audit_id: string
  status: string
  resumen: string
  hallazgos: string
  conclusiones: string
  recomendaciones: string
}

export interface GeneratedAuditReport extends AuditReportDraft {
  references: ReportReference[]
}

export interface ReportSections {
  resumen: string
  hallazgos: string
  conclusiones: string
  recomendaciones: string
}

export const getLatestReport = (auditId: string): Promise<AuditReportDraft> => {
  const params = new URLSearchParams({ audit_id: auditId })
  return apiRequest<AuditReportDraft>(`/api/v1/ai/reports?${params.toString()}`)
}

export const generateReport = (auditId: string): Promise<GeneratedAuditReport> =>
  apiRequest<GeneratedAuditReport>('/api/v1/ai/reports/generate', {
    method: 'POST',
    body: JSON.stringify({ audit_id: auditId }),
  })

export const updateReport = (
  reportId: string,
  sections: ReportSections,
): Promise<AuditReportDraft> =>
  apiRequest<AuditReportDraft>(`/api/v1/ai/reports/${reportId}`, {
    method: 'PATCH',
    body: JSON.stringify(sections),
  })
