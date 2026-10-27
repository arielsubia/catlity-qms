import { Alert, Button, Form, Select, Space, Table, Tag, Typography } from 'antd'
import { useContext, useEffect, useState } from 'react'

import { listAudits, type Audit } from '../api/audits-api'
import { listFindings, type Finding } from '../api/findings-api'
import { ApiError } from '../api/http'
import { useAuth } from '../auth/use-auth'
import { OpenFindingsContext } from '../findings/open-findings-context'
import {
  FINDING_STATUSES,
  FINDING_TYPES,
  assigneeLabel,
  auditLabel,
  filterByResponsible,
  statusLabel,
  typeColor,
  typeLabel,
  type ResponsibleFilter,
} from '../findings/finding-view'
import { canCreateFinding, canEditFinding } from '../findings/permissions'
import { FindingDetailDrawer } from './finding-detail-drawer'
import { FindingFormDrawer } from './finding-form-drawer'

const PAGE_SIZE = 10

type FormState = { mode: 'create' } | { mode: 'edit'; finding: Finding } | null

export const FindingsPage = () => {
  const { user } = useAuth()
  const openFindings = useContext(OpenFindingsContext)
  const [findings, setFindings] = useState<Finding[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [typeFilter, setTypeFilter] = useState<string | undefined>(undefined)
  const [statusFilter, setStatusFilter] = useState<string | undefined>(undefined)
  const [responsibleFilter, setResponsibleFilter] = useState<ResponsibleFilter>('all')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [auditsError, setAuditsError] = useState<string | null>(null)
  const [reloadKey, setReloadKey] = useState(0)
  const [audits, setAudits] = useState<Audit[]>([])
  const [auditsTruncated, setAuditsTruncated] = useState(false)
  const [form, setForm] = useState<FormState>(null)
  const [viewingId, setViewingId] = useState<string | null>(null)

  useEffect(() => {
    if (!user) {
      return
    }
    let active = true
    void listAudits({ skip: 0, limit: 100 })
      .then((result) => {
        if (!active) {
          return
        }
        setAudits(result.items)
        setAuditsTruncated(result.total > result.items.length)
      })
      .catch((err: unknown) => {
        if (!active) {
          return
        }
        setAudits([])
        setAuditsError(err instanceof ApiError ? err.message : 'Could not load audits.')
      })
    return () => {
      active = false
    }
  }, [user])

  useEffect(() => {
    if (!user) {
      return
    }
    let active = true
    void listFindings({
      skip: (page - 1) * PAGE_SIZE,
      limit: PAGE_SIZE,
      ...(typeFilter ? { findingType: typeFilter } : {}),
      ...(statusFilter ? { status: statusFilter } : {}),
    })
      .then((result) => {
        if (!active) {
          return
        }
        setFindings(result.items)
        setTotal(result.total)
        setError(null)
      })
      .catch((err: unknown) => {
        if (active) {
          setError(err instanceof ApiError ? err.message : 'Could not load findings.')
        }
      })
      .finally(() => {
        if (active) {
          setLoading(false)
        }
      })
    return () => {
      active = false
    }
  }, [user, page, typeFilter, statusFilter, reloadKey])

  if (!user) {
    return null
  }

  const visibleFindings = filterByResponsible(findings, responsibleFilter)
  const viewing = findings.find((item) => item.id === viewingId) ?? null
  const replaceFinding = (next: Finding) => {
    setFindings((current) => current.map((item) => (item.id === next.id ? next : item)))
  }

  return (
    <>
      <div className="audits-header">
        <Typography.Title level={2}>Findings</Typography.Title>
        {canCreateFinding(user.role) && (
          <Button type="primary" onClick={() => setForm({ mode: 'create' })}>
            New finding
          </Button>
        )}
      </div>
      {error && <Alert type="error" showIcon className="auth-alert" title={error} />}
      {auditsError && <Alert type="error" showIcon className="auth-alert" title={auditsError} />}
      <Form layout="inline" className="audits-toolbar">
        <Form.Item label="Type">
          <Select
            allowClear
            virtual={false}
            placeholder="All types"
            aria-label="Type"
            value={typeFilter}
            style={{ minWidth: 220 }}
            options={FINDING_TYPES.map((findingType) => ({
              value: findingType,
              label: typeLabel(findingType),
            }))}
            onChange={(value: string | undefined) => {
              setLoading(true)
              setTypeFilter(value)
              setPage(1)
            }}
          />
        </Form.Item>
        <Form.Item label="Status">
          <Select
            allowClear
            virtual={false}
            placeholder="All statuses"
            aria-label="Status"
            value={statusFilter}
            style={{ minWidth: 180 }}
            options={FINDING_STATUSES.map((status) => ({
              value: status,
              label: statusLabel(status),
            }))}
            onChange={(value: string | undefined) => {
              setLoading(true)
              setStatusFilter(value)
              setPage(1)
            }}
          />
        </Form.Item>
        <Form.Item label="Responsible">
          <Select
            virtual={false}
            aria-label="Responsible"
            value={responsibleFilter}
            style={{ minWidth: 180 }}
            options={[
              { value: 'all', label: 'All' },
              { value: 'unassigned', label: 'Unassigned' },
            ]}
            onChange={(value: ResponsibleFilter) => setResponsibleFilter(value)}
          />
        </Form.Item>
      </Form>
      <Typography.Paragraph type="secondary" className="audits-note">
        The responsible filter applies to the findings already loaded on this page. Findings are
        created without an assignee.
      </Typography.Paragraph>
      <Table<Finding>
        rowKey="id"
        loading={loading}
        dataSource={visibleFindings}
        pagination={{
          current: page,
          pageSize: PAGE_SIZE,
          total,
          showSizeChanger: false,
          onChange: (nextPage) => {
            setLoading(true)
            setPage(nextPage)
          },
        }}
        locale={{
          emptyText:
            findings.length > 0 && visibleFindings.length === 0
              ? 'No findings on this page match the responsible filter.'
              : 'No findings yet.',
        }}
        columns={[
          { title: 'Title', dataIndex: 'title' },
          {
            title: 'Type',
            dataIndex: 'finding_type',
            render: (findingType: string) => (
              <Tag color={typeColor(findingType)}>{typeLabel(findingType)}</Tag>
            ),
          },
          {
            title: 'Status',
            dataIndex: 'status',
            render: (status: string) => statusLabel(status),
          },
          {
            title: 'Audit',
            dataIndex: 'audit_id',
            render: (auditId: string) => auditLabel(auditId, audits),
          },
          {
            title: 'Responsible',
            dataIndex: 'assignee_id',
            render: (assigneeId: string | null) => assigneeLabel(assigneeId),
          },
          {
            title: 'Actions',
            key: 'actions',
            render: (_, record) => (
              <Space>
                <Button type="link" onClick={() => setViewingId(record.id)}>
                  View
                </Button>
                {canEditFinding(user.role) && (
                  <Button type="link" onClick={() => setForm({ mode: 'edit', finding: record })}>
                    Edit
                  </Button>
                )}
              </Space>
            ),
          },
        ]}
      />
      {viewing && (
        <FindingDetailDrawer
          finding={viewing}
          role={user.role}
          auditTitle={auditLabel(viewing.audit_id, audits)}
          onClose={() => setViewingId(null)}
          onEdit={(row) => {
            setViewingId(null)
            setForm({ mode: 'edit', finding: row })
          }}
          onUpdated={(next) => {
            replaceFinding(next)
            openFindings?.refresh()
          }}
        />
      )}
      {form && (
        <FindingFormDrawer
          mode={form.mode}
          finding={form.mode === 'edit' ? form.finding : null}
          audits={audits}
          auditsTruncated={auditsTruncated}
          onClose={() => setForm(null)}
          onSaved={(saved) => {
            if (form.mode === 'create') {
              setForm(null)
              setLoading(true)
              setPage(1)
              setReloadKey((key) => key + 1)
              openFindings?.refresh()
              return
            }
            replaceFinding(saved)
            setForm(null)
          }}
        />
      )}
    </>
  )
}
