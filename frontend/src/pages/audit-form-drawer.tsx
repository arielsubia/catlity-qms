import { Alert, Button, Drawer, Form, Input } from 'antd'
import { useState } from 'react'

import { createAudit, updateAudit, type Audit, type AuditDraft } from '../api/audits-api'
import { ApiError } from '../api/http'

interface AuditFormValues {
  name: string
  description?: string
  type: string
  plannedDate?: string
}

interface AuditFormDrawerProps {
  mode: 'create' | 'edit'
  audit: Audit | null
  onClose: () => void
  onSaved: (audit: Audit) => void
}

const toDraft = (values: AuditFormValues): AuditDraft => ({
  title: values.name.trim(),
  description: values.description?.trim() ? values.description.trim() : null,
  auditType: values.type.trim(),
  plannedDate: values.plannedDate || null,
})

export const AuditFormDrawer = ({ mode, audit, onClose, onSaved }: AuditFormDrawerProps) => {
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const isCreate = mode === 'create'

  const handleFinish = async (values: AuditFormValues) => {
    setError(null)
    setSubmitting(true)
    try {
      const saved = isCreate
        ? await createAudit(toDraft(values))
        : await updateAudit(audit?.id ?? '', toDraft(values))
      onSaved(saved)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not save the audit.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Drawer
      title={isCreate ? 'New audit' : 'Edit audit'}
      open
      size="large"
      onClose={onClose}
      destroyOnHidden
    >
      {error && <Alert type="error" showIcon className="auth-alert" title={error} />}
      <Form<AuditFormValues>
        layout="vertical"
        initialValues={{
          name: audit?.title ?? '',
          description: audit?.description ?? '',
          type: audit?.audit_type ?? 'internal',
          plannedDate: audit?.planned_date ?? '',
        }}
        onFinish={handleFinish}
      >
        <Form.Item
          label="Name"
          name="name"
          rules={[
            {
              validator: (_, value: string) =>
                value?.trim()
                  ? Promise.resolve()
                  : Promise.reject(new Error('Please enter a name.')),
            },
          ]}
        >
          <Input />
        </Form.Item>
        <Form.Item label="Description" name="description">
          <Input.TextArea rows={3} />
        </Form.Item>
        <Form.Item
          label="Type"
          name="type"
          rules={[
            {
              validator: (_, value: string) =>
                value?.trim()
                  ? Promise.resolve()
                  : Promise.reject(new Error('Please enter a type.')),
            },
          ]}
        >
          <Input />
        </Form.Item>
        <Form.Item label="Planned date" name="plannedDate">
          <Input type="date" />
        </Form.Item>
        <Button type="primary" htmlType="submit" loading={submitting}>
          {isCreate ? 'Create audit' : 'Save changes'}
        </Button>
      </Form>
    </Drawer>
  )
}
