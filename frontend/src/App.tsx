import { Flex, Typography } from 'antd'
import { useState } from 'react'

import { useAuth } from './auth/use-auth'
import { AppLayout } from './layout/app-layout'
import { LoginPage } from './pages/login-page'
import { RegisterPage } from './pages/register-page'

type AuthView = 'login' | 'register'

const App = () => {
  const { user } = useAuth()
  const [view, setView] = useState<AuthView>('login')

  if (user) {
    return <AppLayout />
  }

  return (
    <Flex vertical align="center" justify="center" gap="middle" className="app-shell">
      <Typography.Title>Catlity QMS</Typography.Title>
      {view === 'register' ? (
        <RegisterPage onSwitchToLogin={() => setView('login')} />
      ) : (
        <LoginPage onSwitchToRegister={() => setView('register')} />
      )}
    </Flex>
  )
}

export default App
