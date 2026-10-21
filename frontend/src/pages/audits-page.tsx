import { Alert, Button, Form, Input, Select, Space, Table, Typography } from 'antd'
import { useEffect, useState } from 'react'

import { listAuditors, listAudits, type Audit, type AvailableAuditor } from '../api/audits-api'
import { ApiError } from '../api/http'
import { useAuth } from '../auth/use-auth'
import {
  AUDIT_STATUSES,
  auditorLabel,
  filterByPlannedDate,
  statusLabel,
} from '../audits/audit-view'
import { canCreateAudit, canEditAudit, canListAuditors } from '../audits/permissions'
import { AuditDetailDrawer } from './audit-detail-drawer'
import { AuditFormDrawer } from './audit-form-drawer'

const PAGE_SIZE = 10

type FormState = { mode: 'create' } | { mode: 'edit'; audit: Audit } | null

export const AuditsPage = () => {
  const { user } = useAuth()
  const [audits, setAudits] = useState<Audit[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [statusFilter, setStatusFilter] = useState<string | undefined>(undefined)
  const [fromDate, setFromDate] = useState('')
  const [toDate, setToDate] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [auditorError, setAuditorError] = useState<string | null>(null)
  const [reloadKey, setReloadKey] = useState(0)
  const [auditors, setAuditors] = useState<AvailableAuditor[] | null>(null)
  const [form, setForm] = useState<FormState>(null)
  const [viewingId, setViewingId] = useState<string | null>(null)

  useEffect(() => {
    if (!user || !canListAuditors(user.role)) {
      return
    }
    let active = true
    void listAuditors()
      .then((rows) => {
        if (active) {
          setAuditors(rows)
        }
      })
      .catch((err: unknown) => {
        if (!active) {
          return
        }
        setAuditors([])
        setAuditorError(err instanceof ApiError ? err.message : 'Could not load auditors.')
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
    void listAudits({
      skip: (page - 1) * PAGE_SIZE,
      limit: PAGE_SIZE,
      status: statusFilter,
    })
      .then((result) => {
        if (!active) {
          return
        }
        setAudits(result.items)
        setTotal(result.total)
        setError(null)
      })
      .catch((err: unknown) => {
        if (active) {
          setError(err instanceof ApiError ? err.message : 'Could not load audits.')
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
  }, [user, page, statusFilter, reloadKey])

  if (!user) {
    return null
  }

  const visibleAudits = filterByPlannedDate(audits, fromDate, toDate)
  const replaceAudit = (next: Audit) => {
    setAudits((current) => current.map((item) => (item.id === next.id ? next : item)))
  }

  return (
    <>
      <div className="audits-header">
        <Typography.Title level={2}>Audits</Typography.Title>
        {canCreateAudit(user.role) && (
          <Button type="primary" onClick={() => setForm({ mode: 'create' })}>
            New audit
          </Button>
        )}
      </div>
      {error && <Alert type="error" showIcon className="auth-alert" title={error} />}
      {auditorError && <Alert type="error" showIcon className="auth-alert" title={auditorError} />}
      <Form layout="inline" className="audits-toolbar">
        <Form.Item label="Status">
          <Select
            allowClear
            virtual={false}
            placeholder="All statuses"
            aria-label="Status"
            value={statusFilter}
            style={{ minWidth: 180 }}
            options={AUDIT_STATUSES.map((status) => ({
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
        <Form.Item label="From">
          <Input
            type="date"
            aria-label="From"
            value={fromDate}
            onChange={(event) => setFromDate(event.target.value)}
          />
        </Form.Item>
        <Form.Item label="To">
          <Input
            type="date"
            aria-label="To"
            value={toDate}
            onChange={(event) => setToDate(event.target.value)}
          />
        </Form.Item>
      </Form>
      <Typography.Paragraph type="secondary" className="audits-note">
        The date range filters the audits already loaded on this page.
      </Typography.Paragraph>
      <Table<Audit>
        rowKey="id"
        loading={loading}
        dataSource={visibleAudits}
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
            audits.length > 0 && visibleAudits.length === 0
              ? 'No audits on this page match the date range.'
              : 'No audits yet.',
        }}
        columns={[
          { title: 'Name', dataIndex: 'title' },
          {
            title: 'Status',
            dataIndex: 'status',
            render: (status: string) => statusLabel(status),
          },
          {
            title: 'Auditor',
            dataIndex: 'auditor_id',
            render: (auditorId: string | null) => auditorLabel(auditorId, auditors),
          },
          {
            title: 'Date',
            dataIndex: 'planned_date',
            render: (plannedDate: string | null) => plannedDate ?? 'Not set',
          },
          {
            title: 'Actions',
            key: 'actions',
            render: (_, record) => (
              <Space>
                <Button type="link" onClick={() => setViewingId(record.id)}>
                  View
                </Button>
                {canEditAudit(user.role) && (
                  <Button type="link" onClick={() => setForm({ mode: 'edit', audit: record })}>
                    Edit
                  </Button>
                )}
              </Space>
            ),
          },
        ]}
      />
      {viewingId && (
        <AuditDetailDrawer
          auditId={viewingId}
          role={user.role}
          auditors={auditors}
          onClose={() => setViewingId(null)}
          onEdit={(audit) => {
            setViewingId(null)
            setForm({ mode: 'edit', audit })
          }}
          onUpdated={replaceAudit}
        />
      )}
      {form && (
        <AuditFormDrawer
          mode={form.mode}
          audit={form.mode === 'edit' ? form.audit : null}
          onClose={() => setForm(null)}
          onSaved={(saved) => {
            if (form.mode === 'create') {
              setForm(null)
              setLoading(true)
              setPage(1)
              setReloadKey((key) => key + 1)
              return
            }
            replaceAudit(saved)
            setForm(null)
          }}
        />
      )}
    </>
  )
}
