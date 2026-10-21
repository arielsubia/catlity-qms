import { Alert, Button, Drawer, Select, Space, Steps, Typography } from 'antd'
import { useEffect, useState } from 'react'

import {
  assignAuditor,
  getAudit,
  updateAuditStatus,
  type Audit,
  type AvailableAuditor,
} from '../api/audits-api'
import { ApiError } from '../api/http'
import {
  AUDIT_STATUSES,
  auditorLabel,
  formatStatusChangedAt,
  nextStatus,
  statusLabel,
} from '../audits/audit-view'
import { canAssignAuditor, canChangeStatus, canEditAudit } from '../audits/permissions'

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
        </>
      )}
    </Drawer>
  )
}
