import { Button, Layout, Menu, Typography } from 'antd'
import { useState } from 'react'

import { useAuth } from '../auth/use-auth'
import { NAV_ITEMS, type SectionKey } from './nav-items'

const { Content, Header, Sider } = Layout

const isSectionKey = (key: string): key is SectionKey => NAV_ITEMS.some((item) => item.key === key)

export const AppLayout = () => {
  const { user, signOut } = useAuth()
  const [section, setSection] = useState<SectionKey>('dashboard')
  const [collapsed, setCollapsed] = useState(false)
  const [isCompact, setIsCompact] = useState(false)
  const [signingOut, setSigningOut] = useState(false)

  const current = NAV_ITEMS.find((item) => item.key === section) ?? NAV_ITEMS[0]

  const handleSignOut = async () => {
    setSigningOut(true)
    try {
      await signOut()
    } finally {
      setSigningOut(false)
    }
  }

  const handleMenuClick = ({ key }: { key: string }) => {
    if (!isSectionKey(key)) {
      return
    }
    setSection(key)
    if (isCompact) {
      setCollapsed(true)
    }
  }

  if (!user) {
    return null
  }

  return (
    <Layout className="app-layout">
      <Header
        className="app-header"
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 16,
          height: 'auto',
          minHeight: 64,
          padding: '12px 16px',
          lineHeight: 1.4,
          background: '#fff',
          color: 'rgba(0, 0, 0, 0.88)',
        }}
      >
        {isCompact && (
          <Button onClick={() => setCollapsed((isCollapsed) => !isCollapsed)}>
            {collapsed ? 'Open menu' : 'Close menu'}
          </Button>
        )}
        <div className="app-header-user">
          <Typography.Text>{user.email}</Typography.Text>
          <Typography.Text>{user.role}</Typography.Text>
          <Typography.Text>
            <Typography.Text type="secondary">Organization</Typography.Text> {user.tenantId}
          </Typography.Text>
        </div>
        <Button onClick={handleSignOut} loading={signingOut}>
          Sign out
        </Button>
      </Header>
      <Layout className="app-body">
        <Sider
          collapsible
          collapsed={collapsed}
          breakpoint="lg"
          collapsedWidth={0}
          trigger={isCompact ? null : undefined}
          onBreakpoint={setIsCompact}
          onCollapse={setCollapsed}
        >
          <div className="app-sider-brand">Catlity QMS</div>
          <Menu
            theme="dark"
            mode="inline"
            selectedKeys={[section]}
            items={NAV_ITEMS.map((item) => ({ key: item.key, label: item.label }))}
            onClick={handleMenuClick}
          />
        </Sider>
        <Content className="app-content">
          <Typography.Title level={2}>{current.label}</Typography.Title>
          <Typography.Paragraph>This section is not available yet.</Typography.Paragraph>
        </Content>
      </Layout>
    </Layout>
  )
}
