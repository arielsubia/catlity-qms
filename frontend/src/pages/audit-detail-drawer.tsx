import { Alert, Button, Drawer, Select, Space, Steps, Typography } from 'antd'
import { useEffect, useRef, useState } from 'react'
import { flushSync } from 'react-dom'

import {
  assignAuditor,
  getAudit,
  updateAuditStatus,
  type Audit,
  type AvailableAuditor,
} from '../api/audits-api'
import { ApiError } from '../api/http'
import {
  generateReport,
  getLatestReport,
  updateReport,
  type AuditReportDraft,
  type ReportReference,
  type ReportSections,
} from '../api/reports-api'
import {
  AUDIT_STATUSES,
  auditorLabel,
  formatStatusChangedAt,
  nextStatus,
  statusLabel,
} from '../audits/audit-view'
import {
  canAssignAuditor,
  canChangeStatus,
  canEditAudit,
  canGenerateReport,
} from '../audits/permissions'
import { REPORT_SECTIONS, sectionsHaveText } from '../reports/report-html'

import { ReportEditor, type ReportEditorHandle } from './report-editor'

interface AuditDetailDrawerProps {
  auditId: string
  role: string
  auditors: AvailableAuditor[] | null
  onClose: () => void
  onEdit: (audit: Audit) => void
  onUpdated: (audit: Audit) => void
}

const actionMessage = (err: unknown, fallback: string): string =>
  err instanceof ApiError ? err.message : fallback

export const AuditDetailDrawer = ({
  auditId,
  role,
  auditors,
  onClose,
  onEdit,
  onUpdated,
}: AuditDetailDrawerProps) => {
  const [audit, setAudit] = useState<Audit | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)
  const [assigneeId, setAssigneeId] = useState<string | undefined>(undefined)
  const [moving, setMoving] = useState(false)
  const [assigning, setAssigning] = useState(false)
  const [report, setReport] = useState<AuditReportDraft | null>(null)
  const [references, setReferences] = useState<ReportReference[]>([])
  const [reportLoaded, setReportLoaded] = useState(false)
  const [generating, setGenerating] = useState(false)
  const [saving, setSaving] = useState(false)
  const [printSections, setPrintSections] = useState<ReportSections | null>(null)
  const editorRef = useRef<ReportEditorHandle>(null)
  const requestSeq = useRef(0)

  useEffect(() => {
    let active = true
    void getAudit(auditId)
      .then((row) => {
        if (!active) {
          return
        }
        setAudit(row)
        const known = auditors?.some((auditor) => auditor.id === row.auditor_id) ?? false
        setAssigneeId(known ? (row.auditor_id ?? undefined) : undefined)
      })
      .catch((err: unknown) => {
        if (active) {
          setLoadError(actionMessage(err, 'Could not load this audit.'))
        }
      })
    return () => {
      active = false
    }
  }, [auditId, auditors])

  const showReport = audit !== null && audit.status === 'completed' && canGenerateReport(role)

  useEffect(() => {
    if (!showReport || !audit) {
      return
    }
    const seq = ++requestSeq.current
    void getLatestReport(audit.id)
      .then((row) => {
        if (seq !== requestSeq.current) {
          return
        }
        setReport(row)
        setReferences([])
        setReportLoaded(true)
      })
      .catch((err: unknown) => {
        if (seq !== requestSeq.current) {
          return
        }
        if (err instanceof ApiError && err.status === 404) {
          setReport(null)
          setReportLoaded(true)
          return
        }
        setReportLoaded(true)
        setActionError(actionMessage(err, 'Could not load the report.'))
      })
    return () => {
      requestSeq.current += 1
    }
  }, [showReport, audit])

  const upcoming = audit ? nextStatus(audit.status) : null
  const currentIndex = audit
    ? AUDIT_STATUSES.indexOf(audit.status as (typeof AUDIT_STATUSES)[number])
    : 0

  const handleStatus = async () => {
    if (!audit || !upcoming) {
      return
    }
    setActionError(null)
    setMoving(true)
    try {
      const updated = await updateAuditStatus(audit.id, upcoming)
      setAudit(updated)
      onUpdated(updated)
    } catch (err) {
      setActionError(actionMessage(err, 'Could not change the status.'))
    } finally {
      setMoving(false)
    }
  }

  const handleAssign = async () => {
    if (!audit || !assigneeId) {
      return
    }
    setActionError(null)
    setAssigning(true)
    try {
      const updated = await assignAuditor(audit.id, assigneeId)
      setAudit(updated)
      onUpdated(updated)
    } catch (err) {
      setActionError(actionMessage(err, 'Could not assign the auditor.'))
    } finally {
      setAssigning(false)
    }
  }

  const handleGenerate = async () => {
    if (!audit) {
      return
    }
    const seq = ++requestSeq.current
    setActionError(null)
    setGenerating(true)
    try {
      const created = await generateReport(audit.id)
      if (seq !== requestSeq.current) {
        return
      }
      setReport(created)
      setReferences(created.references)
      setReportLoaded(true)
    } catch (err) {
      setActionError(actionMessage(err, 'Could not generate the report.'))
    } finally {
      setGenerating(false)
    }
  }

  const readSections = (): ReportSections | null => {
    const sections = editorRef.current?.readSections()
    if (!sections || !sectionsHaveText(sections)) {
      setActionError('Each section needs text.')
      return null
    }
    return sections
  }

  const handleSave = async () => {
    if (!report) {
      return
    }
    const sections = readSections()
    if (!sections) {
      return
    }
    setActionError(null)
    setSaving(true)
    try {
      const updated = await updateReport(report.id, sections)
      setReport(updated)
    } catch (err) {
      setActionError(actionMessage(err, 'Could not save the report.'))
    } finally {
      setSaving(false)
    }
  }

  const handleExport = () => {
    const sections = readSections()
    if (!sections) {
      return
    }
    setActionError(null)
    flushSync(() => setPrintSections(sections))
    if (typeof window.print === 'function') {
      window.print()
    }
    setPrintSections(null)
  }

  return (
    <Drawer title={audit?.title ?? 'Audit'} open size="large" onClose={onClose} destroyOnHidden>
      {loadError && <Alert type="error" showIcon title={loadError} />}
      {audit && (
        <>
          <Steps
            current={currentIndex < 0 ? 0 : currentIndex}
            items={AUDIT_STATUSES.map((status) => ({ title: statusLabel(status) }))}
          />
          <Typography.Paragraph className="audits-note">
            {audit.status_changed_at
              ? `Last status change: ${formatStatusChangedAt(audit.status_changed_at)}`
              : 'No status change recorded yet.'}
          </Typography.Paragraph>
          <Typography.Paragraph>
            <Typography.Text type="secondary">Type </Typography.Text>
            {audit.audit_type}
          </Typography.Paragraph>
          <Typography.Paragraph>
            <Typography.Text type="secondary">Date </Typography.Text>
            {audit.planned_date ?? 'Not set'}
          </Typography.Paragraph>
          <Typography.Paragraph>
            <Typography.Text type="secondary">Auditor </Typography.Text>
            {auditorLabel(audit.auditor_id, auditors)}
          </Typography.Paragraph>
          <Typography.Paragraph>{audit.description ?? 'No description.'}</Typography.Paragraph>
          {actionError && (
            <Alert type="error" showIcon className="auth-alert" title={actionError} />
          )}
          <Space wrap>
            {canEditAudit(role) && <Button onClick={() => onEdit(audit)}>Edit</Button>}
            {canChangeStatus(role) && upcoming && (
              <Button type="primary" loading={moving} onClick={handleStatus}>
                {`Move to ${statusLabel(upcoming).toLowerCase()}`}
              </Button>
            )}
          </Space>
          {canAssignAuditor(role) && (
            <div className="audits-assign">
              {auditors === null ? (
                <Typography.Paragraph>Loading auditors.</Typography.Paragraph>
              ) : auditors.length === 0 ? (
                <Typography.Paragraph>No active auditors are available.</Typography.Paragraph>
              ) : (
                <Space wrap>
                  <Select
                    aria-label="Auditor"
                    virtual={false}
                    placeholder="Select an auditor"
                    value={assigneeId}
                    onChange={setAssigneeId}
                    options={auditors.map((auditor) => ({
                      value: auditor.id,
                      label: auditor.full_name,
                    }))}
                    style={{ minWidth: 220 }}
                  />
                  <Button
                    type="primary"
                    disabled={!assigneeId}
                    loading={assigning}
                    onClick={handleAssign}
                  >
                    Assign auditor
                  </Button>
                </Space>
              )}
            </div>
          )}
          {showReport && (
            <div className="report-panel">
              <Typography.Paragraph type="secondary">
                Generar informe writes a new draft. Save report and Export PDF do not call AWS.
              </Typography.Paragraph>
              <Button loading={generating} onClick={handleGenerate}>
                Generar informe
              </Button>
              {!reportLoaded && <Typography.Paragraph>Loading report.</Typography.Paragraph>}
              {report && <ReportEditor ref={editorRef} draft={report} references={references} />}
              {report && (
                <Space wrap className="report-actions">
                  <Button
                    type="primary"
                    loading={saving}
                    disabled={generating}
                    onClick={handleSave}
                  >
                    Save report
                  </Button>
                  <Button disabled={generating || saving} onClick={handleExport}>
                    Export PDF
                  </Button>
                </Space>
              )}
            </div>
          )}
          {printSections && (
            <article className="report-sheet" aria-hidden="true">
              <p className="report-sheet-kicker">Catlity QMS</p>
              <h1>{audit.title}</h1>
              <p>Audit report · Draft</p>
              <p>
                {audit.planned_date
                  ? `Planned date: ${audit.planned_date}`
                  : 'Planned date: Not set'}
              </p>
              <div className="report-sheet-rule" />
              {REPORT_SECTIONS.map((section) => (
                <section key={section.key}>
                  <h2>{section.label}</h2>
                  <div dangerouslySetInnerHTML={{ __html: printSections[section.key] }} />
                </section>
              ))}
              <p className="report-sheet-footer">Catlity QMS · Draft</p>
            </article>
          )}
        </>
      )}
    </Drawer>
  )
}
