import type { ReactNode } from 'react'

import { PhilCredit } from './phil-credit'
import { PresentationBanner } from './presentation-banner'

export const PresentationFrame = ({ children }: { children: ReactNode }) => (
  <div className="presentation-frame">
    <PresentationBanner />
    <div className="presentation-body">{children}</div>
    <PhilCredit />
  </div>
)
