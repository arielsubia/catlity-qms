import { Flex, Typography } from 'antd'
import { Outlet } from 'react-router-dom'

export const PublicLayout = () => (
  <Flex vertical align="center" justify="center" gap="middle" className="app-shell">
    <Typography.Title>Catlity QMS</Typography.Title>
    <Outlet />
  </Flex>
)
