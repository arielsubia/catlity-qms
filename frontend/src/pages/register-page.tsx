import { Alert, Button, Card, Form, Input, Typography } from 'antd'
import { useState } from 'react'

import { RegisterError, registerUser, type RegisterInput } from '../api/auth-api'

const MIN_PASSWORD_LENGTH = 12

interface RegisterPageProps {
  onSwitchToLogin: () => void
}

export const RegisterPage = ({ onSwitchToLogin }: RegisterPageProps) => {
  const [error, setError] = useState<string | null>(null)
  const [registered, setRegistered] = useState(false)
  const [submitting, setSubmitting] = useState(false)

  const handleFinish = async (values: RegisterInput) => {
    setError(null)
    setSubmitting(true)
    try {
      await registerUser(values)
      setRegistered(true)
    } catch (err) {
      setError(err instanceof RegisterError ? err.message : 'Unexpected error while registering.')
    } finally {
      setSubmitting(false)
    }
  }

  if (registered) {
    return (
      <Card title="Account created" className="auth-card">
        <Alert type="success" showIcon className="auth-alert" title="You can sign in now." />
        <Button type="primary" block onClick={onSwitchToLogin}>
          Go to sign in
        </Button>
      </Card>
    )
  }

  return (
    <Card title="Create your account" className="auth-card">
      {error && <Alert type="error" showIcon className="auth-alert" title={error} />}
      <Form<RegisterInput> layout="vertical" onFinish={handleFinish} requiredMark={false}>
        <Form.Item
          label="Full name"
          name="fullName"
          rules={[{ required: true, whitespace: true, message: 'Please enter your full name.' }]}
        >
          <Input autoComplete="name" />
        </Form.Item>
        <Form.Item
          label="Email"
          name="email"
          rules={[
            { required: true, message: 'Please enter your email.' },
            { type: 'email', message: 'Please enter a valid email.' },
          ]}
        >
          <Input autoComplete="email" />
        </Form.Item>
        <Form.Item
          label="Password"
          name="password"
          rules={[
            { required: true, message: 'Please enter a password.' },
            {
              min: MIN_PASSWORD_LENGTH,
              message: `The password must have at least ${MIN_PASSWORD_LENGTH} characters.`,
            },
          ]}
        >
          <Input.Password autoComplete="new-password" />
        </Form.Item>
        <Form.Item
          label="Organization ID"
          name="tenantId"
          extra="Provided by your organization administrator."
          rules={[
            { required: true, whitespace: true, message: 'Please enter your organization ID.' },
          ]}
        >
          <Input />
        </Form.Item>
        <Button type="primary" htmlType="submit" block loading={submitting}>
          Create account
        </Button>
      </Form>
      <Typography.Paragraph className="auth-switch">
        Already have an account?{' '}
        <Button type="link" onClick={onSwitchToLogin}>
          Sign in
        </Button>
      </Typography.Paragraph>
    </Card>
  )
}
