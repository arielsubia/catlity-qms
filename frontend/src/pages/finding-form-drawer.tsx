import { Alert, Button, Drawer, Form, Input, Select, Typography } from 'antd'
import { useState } from 'react'

import { createFinding, updateFinding, type Finding, type FindingDraft } from '../api/findings-api'
import { ApiError } from '../api/http'
import { FINDING_TYPES, auditLabel, type AuditTitle, typeLabel } from '../findings/finding-view'

interface FindingFormValues {
  auditId?: string
  title: string
  description?: string
  findingType: string
  severity: string
  clauseReference?: string
}

interface FindingFormDrawerProps {
  mode: 'create' | 'edit'
  finding: Finding | null
  audits: AuditTitle[]
  auditsTruncated: boolean
  onClose: () => void
  onSaved: (finding: Finding) => void
}

const toDraft = (values: FindingFormValues): FindingDraft => ({
  title: values.title.trim(),
  description: values.description?.trim() ? values.description.trim() : null,
  findingType: values.findingType,
  severity: values.severity.trim(),
  clauseReference: values.clauseReference?.trim() ? values.clauseReference.trim() : null,
})

export const FindingFormDrawer = ({
  mode,
  finding,
  audits,
  auditsTruncated,
  onClose,
  onSaved,
}: FindingFormDrawerProps) => {
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const isCreate = mode === 'create'

  const handleFinish = async (values: FindingFormValues) => {
    const auditId = values.auditId
    if (isCreate && !auditId) {
      return
    }
    setError(null)
    setSubmitting(true)
    try {
      const draft = toDraft(values)
      const saved =
        isCreate && auditId
          ? await createFinding(auditId, draft)
          : await updateFinding(finding?.id ?? '', draft)
      onSaved(saved)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not save the finding.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Drawer
      title={isCreate ? 'New finding' : 'Edit finding'}
      open
      size="large"
      onClose={onClose}
      destroyOnHidden
    >
      {error && <Alert type="error" showIcon className="auth-alert" title={error} />}
      {!isCreate && finding && (
        <Typography.Paragraph>
          <Typography.Text type="secondary">Audit </Typography.Text>
          {auditLabel(finding.audit_id, audits)}
        </Typography.Paragraph>
      )}
      {isCreate && audits.length === 0 && (
        <Typography.Paragraph>No audits are available.</Typography.Paragraph>
      )}
      {isCreate && auditsTruncated && (
        <Typography.Paragraph className="audits-note">
          The audit list shows the first 100 audits.
        </Typography.Paragraph>
      )}
      <Form<FindingFormValues>
        layout="vertical"
        initialValues={{
          title: finding?.title ?? '',
          description: finding?.description ?? '',
          findingType: finding?.finding_type ?? 'minor_nc',
          severity: finding?.severity ?? 'medium',
          clauseReference: finding?.clause_reference ?? '',
        }}
        onFinish={handleFinish}
      >
        {isCreate && (
          <Form.Item
            label="Audit"
            name="auditId"
            rules={[{ required: true, message: 'Please select an audit.' }]}
          >
            <Select
              aria-label="Audit"
              virtual={false}
              placeholder="Select an audit"
              options={audits.map((audit) => ({ value: audit.id, label: audit.title }))}
            />
          </Form.Item>
        )}
        <Form.Item
          label="Title"
          name="title"
          rules={[
            {
              validator: (_, value: string) =>
                value?.trim()
                  ? Promise.resolve()
                  : Promise.reject(new Error('Please enter a title.')),
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
          name="findingType"
          rules={[{ required: true, message: 'Please select a type.' }]}
        >
          <Select
            aria-label="Type"
            virtual={false}
            options={FINDING_TYPES.map((findingType) => ({
              value: findingType,
              label: typeLabel(findingType),
            }))}
          />
        </Form.Item>
        <Form.Item
          label="Severity"
          name="severity"
          rules={[
            {
              validator: (_, value: string) =>
                value?.trim()
                  ? Promise.resolve()
                  : Promise.reject(new Error('Please enter a severity.')),
            },
          ]}
        >
          <Input />
        </Form.Item>
        <Form.Item label="Clause" name="clauseReference">
          <Input />
        </Form.Item>
        <Button
          type="primary"
          htmlType="submit"
          loading={submitting}
          disabled={isCreate && audits.length === 0}
        >
          {isCreate ? 'Create finding' : 'Save changes'}
        </Button>
      </Form>
    </Drawer>
  )
}
