import { Route, Routes } from 'react-router-dom'

import { AppLayout } from '../layout/app-layout'
import { NAV_ITEMS } from '../layout/nav-items'
import { PublicLayout } from '../layout/public-layout'
import { LoginPage } from '../pages/login-page'
import { RegisterPage } from '../pages/register-page'
import { AuditsPage } from '../pages/audits-page'
import { FindingsPage } from '../pages/findings-page'
import { SectionPage } from '../pages/section-page'
import { GuestOnly, RequireAuth, SessionRedirect } from './guards'

const pageFor = (path: string) => {
  if (path === '/audits') {
    return <AuditsPage />
  }
  if (path === '/findings') {
    return <FindingsPage />
  }
  return <SectionPage />
}

export const AppRoutes = () => (
  <Routes>
    <Route element={<GuestOnly />}>
      <Route element={<PublicLayout />}>
        <Route path="login" element={<LoginPage />} />
        <Route path="register" element={<RegisterPage />} />
      </Route>
    </Route>
    <Route element={<RequireAuth />}>
      <Route element={<AppLayout />}>
        {NAV_ITEMS.map((item) => (
          <Route key={item.path} path={item.path.slice(1)} element={pageFor(item.path)} />
        ))}
      </Route>
    </Route>
    <Route path="*" element={<SessionRedirect />} />
  </Routes>
)
