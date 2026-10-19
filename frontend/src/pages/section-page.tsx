import { Typography } from 'antd'
import { useLocation } from 'react-router-dom'

import { NAV_ITEMS } from '../layout/nav-items'

export const SectionPage = () => {
  const { pathname } = useLocation()
  const current = NAV_ITEMS.find((item) => item.path === pathname)

  return (
    <>
      <Typography.Title level={2}>{current?.label}</Typography.Title>
      <Typography.Paragraph>This section is not available yet.</Typography.Paragraph>
    </>
  )
}
