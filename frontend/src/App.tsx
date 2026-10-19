import { BrowserRouter } from 'react-router-dom'

import { AppRoutes } from './routing/app-routes'

const App = () => (
  <BrowserRouter>
    <AppRoutes />
  </BrowserRouter>
)

export default App
