import { Button, Layout, Menu, Typography } from 'antd'
import { useState } from 'react'
import { Link, Outlet, useLocation, useNavigate } from 'react-router-dom'

import { useAuth } from '../auth/use-auth'
import { NAV_ITEMS } from './nav-items'

const { Content, Header, Sider } = Layout

export const AppLayout = () => {
  const { user, signOut } = useAuth()
  const { pathname } = useLocation()
  const navigate = useNavigate()
  const [collapsed, setCollapsed] = useState(false)
  const [isCompact, setIsCompact] = useState(false)
  const [signingOut, setSigningOut] = useState(false)

  const handleSignOut = async () => {
    setSigningOut(true)
    try {
      await signOut()
      navigate('/login', { replace: true })
    } finally {
      setSigningOut(false)
    }
  }

  const handleMenuClick = ({ key }: { key: string }) => {
    const item = NAV_ITEMS.find((entry) => entry.path === key)
    if (!item) {
      return
    }
    navigate(item.path)
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
            selectedKeys={[pathname]}
            items={NAV_ITEMS.map((item) => ({
              key: item.path,
              label: <Link to={item.path}>{item.label}</Link>,
            }))}
            onClick={handleMenuClick}
          />
        </Sider>
        <Content className="app-content">
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  )
}
