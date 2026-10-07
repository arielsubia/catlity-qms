import { Flex, Typography } from 'antd'
import { useState } from 'react'

import { useAuth } from './auth/use-auth'
import { HomePage } from './pages/home-page'
import { LoginPage } from './pages/login-page'
import { RegisterPage } from './pages/register-page'

type AuthView = 'login' | 'register'

const App = () => {
  const { user } = useAuth()
  const [view, setView] = useState<AuthView>('login')

  const renderContent = () => {
    if (user) {
      return <HomePage />
    }
    if (view === 'register') {
      return <RegisterPage onSwitchToLogin={() => setView('login')} />
    }
    return <LoginPage onSwitchToRegister={() => setView('register')} />
  }

  return (
    <Flex vertical align="center" justify="center" gap="middle" className="app-shell">
      <Typography.Title>Catlity QMS</Typography.Title>
      {renderContent()}
    </Flex>
  )
}

export default App
