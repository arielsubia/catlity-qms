import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { PresentationFrame } from './presentation-frame'

describe('PresentationFrame', () => {
  it('shows the academic banner and the Phil Dev credit around the product', () => {
    render(
      <PresentationFrame>
        <h1>Catlity QMS</h1>
      </PresentationFrame>,
    )

    expect(screen.getByRole('img', { name: 'Teclab' })).toBeInTheDocument()
    expect(
      screen.getByText('Trabajo final — Tecnicatura en Cloud Administration'),
    ).toBeInTheDocument()
    expect(screen.getByText('Phil Dev')).toBeInTheDocument()
    expect(screen.getByText('Developed by Phil Dev')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Catlity QMS' })).toBeInTheDocument()
  })
})
