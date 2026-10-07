import { Button, Card, Descriptions } from 'antd'
import { useState } from 'react'

import { useAuth } from '../auth/use-auth'

export const HomePage = () => {
  const { user, signOut } = useAuth()
  const [signingOut, setSigningOut] = useState(false)

  const handleSignOut = async () => {
    setSigningOut(true)
    try {
      await signOut()
    } finally {
      setSigningOut(false)
    }
  }

  return (
    <Card title="You are signed in" className="auth-card">
      <Descriptions column={1} size="small">
        <Descriptions.Item label="Email">{user?.email}</Descriptions.Item>
        <Descriptions.Item label="Organization">{user?.tenantId}</Descriptions.Item>
        <Descriptions.Item label="Role">{user?.role}</Descriptions.Item>
      </Descriptions>
      <Button block onClick={handleSignOut} loading={signingOut}>
        Sign out
      </Button>
    </Card>
  )
}
