import { Alert, Button, Card, Form, Input, Typography } from 'antd'
import { useState } from 'react'

import { AuthServiceError } from '../auth/auth-service'
import { useAuth } from '../auth/use-auth'
import { isAuthConfigured } from '../config/env'

interface LoginFormValues {
  email: string
  password: string
}

interface LoginPageProps {
  onSwitchToRegister: () => void
}

export const LoginPage = ({ onSwitchToRegister }: LoginPageProps) => {
  const { signIn } = useAuth()
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  const handleFinish = async ({ email, password }: LoginFormValues) => {
    setError(null)
    setSubmitting(true)
    try {
      await signIn(email, password)
    } catch (err) {
      setError(err instanceof AuthServiceError ? err.message : 'Unexpected error while signing in.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Card title="Sign in to Catlity QMS" className="auth-card">
      {!isAuthConfigured() && (
        <Alert
          type="warning"
          showIcon
          className="auth-alert"
          title="Cognito is not configured. Set the variables in frontend/.env.local."
        />
      )}
      {error && <Alert type="error" showIcon className="auth-alert" title={error} />}
      <Form<LoginFormValues> layout="vertical" onFinish={handleFinish} requiredMark={false}>
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
          rules={[{ required: true, message: 'Please enter your password.' }]}
        >
          <Input.Password autoComplete="current-password" />
        </Form.Item>
        <Button type="primary" htmlType="submit" block loading={submitting}>
          Sign in
        </Button>
      </Form>
      <Typography.Paragraph className="auth-switch">
        No account yet?{' '}
        <Button type="link" onClick={onSwitchToRegister}>
          Create one
        </Button>
      </Typography.Paragraph>
    </Card>
  )
}
