import { BrowserRouter } from 'react-router-dom'

import { PresentationFrame } from './layout/presentation-frame'
import { AppRoutes } from './routing/app-routes'

const App = () => (
  <BrowserRouter>
    <PresentationFrame>
      <AppRoutes />
    </PresentationFrame>
  </BrowserRouter>
)

export default App
