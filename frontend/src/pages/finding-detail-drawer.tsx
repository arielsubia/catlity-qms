import { Alert, Button, Drawer, Space, Steps, Tag, Typography } from 'antd'
import { useState } from 'react'

import { updateFindingStatus, type Finding } from '../api/findings-api'
import { ApiError } from '../api/http'
import { formatStatusChangedAt } from '../audits/audit-view'
import {
  FINDING_STATUSES,
  assigneeLabel,
  statusActions,
  statusLabel,
  typeColor,
  typeLabel,
} from '../findings/finding-view'
import { canEditFinding } from '../findings/permissions'

interface FindingDetailDrawerProps {
  finding: Finding
  role: string
  auditTitle: string
  onClose: () => void
  onEdit: (finding: Finding) => void
  onUpdated: (finding: Finding) => void
}

const actionMessage = (err: unknown, fallback: string): string =>
  err instanceof ApiError ? err.message : fallback

export const FindingDetailDrawer = ({
  finding,
  role,
  auditTitle,
  onClose,
  onEdit,
  onUpdated,
}: FindingDetailDrawerProps) => {
  const [actionError, setActionError] = useState<string | null>(null)
  const [movingLabel, setMovingLabel] = useState<string | null>(null)
  const actions = statusActions(role, finding.status)
  const currentIndex = FINDING_STATUSES.indexOf(finding.status as (typeof FINDING_STATUSES)[number])
  const showActions = canEditFinding(role) || actions.length > 0

  const handleStatus = async (status: string, label: string) => {
    setActionError(null)
    setMovingLabel(label)
    try {
      onUpdated(await updateFindingStatus(finding.id, status))
    } catch (err) {
      setActionError(actionMessage(err, 'Could not change the status.'))
    } finally {
      setMovingLabel(null)
    }
  }

  return (
    <Drawer title={finding.title} open size="large" onClose={onClose} destroyOnHidden>
      <Steps
        current={currentIndex < 0 ? 0 : currentIndex}
        items={FINDING_STATUSES.map((status) => ({ title: statusLabel(status) }))}
      />
      <Typography.Paragraph className="audits-note">
        {finding.status_changed_at
          ? `Last status change: ${formatStatusChangedAt(finding.status_changed_at)}`
          : 'No status change recorded yet.'}
      </Typography.Paragraph>
      <Typography.Paragraph>
        <Typography.Text type="secondary">Audit </Typography.Text>
        {auditTitle}
      </Typography.Paragraph>
      <Typography.Paragraph>
        <Typography.Text type="secondary">Type </Typography.Text>
        <Tag color={typeColor(finding.finding_type)}>{typeLabel(finding.finding_type)}</Tag>
      </Typography.Paragraph>
      <Typography.Paragraph>
        <Typography.Text type="secondary">Severity </Typography.Text>
        {finding.severity}
      </Typography.Paragraph>
      <Typography.Paragraph>
        <Typography.Text type="secondary">Clause </Typography.Text>
        {finding.clause_reference ?? 'Not set'}
      </Typography.Paragraph>
      <Typography.Paragraph>
        <Typography.Text type="secondary">Responsible </Typography.Text>
        {assigneeLabel(finding.assignee_id)}
      </Typography.Paragraph>
      <Typography.Paragraph>{finding.description ?? 'No description.'}</Typography.Paragraph>
      {actionError && <Alert type="error" showIcon className="auth-alert" title={actionError} />}
      {showActions && (
        <Space wrap>
          {canEditFinding(role) && <Button onClick={() => onEdit(finding)}>Edit</Button>}
          {actions.map((action) => (
            <Button
              key={action.label}
              type={action.label.startsWith('Return') ? 'default' : 'primary'}
              loading={movingLabel === action.label}
              disabled={movingLabel !== null && movingLabel !== action.label}
              onClick={() => handleStatus(action.status, action.label)}
            >
              {action.label}
            </Button>
          ))}
        </Space>
      )}
    </Drawer>
  )
}
