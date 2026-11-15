import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import type { AuditReportDraft } from '../api/reports-api'

import { ReportEditor } from './report-editor'

const draft: AuditReportDraft = {
  id: 'report-1',
  audit_id: 'audit-1',
  status: 'draft',
  resumen: 'Policy gap',
  hallazgos: 'Missing policy',
  conclusiones: 'The policy is missing',
  recomendaciones: 'Publish the policy',
}

describe('ReportEditor', () => {
  it('applies bold, italic, and a list in the focused section', async () => {
    const user = userEvent.setup()
    document.execCommand = vi.fn(() => true)
    render(<ReportEditor draft={draft} references={[]} />)

    expect(await screen.findByRole('textbox', { name: 'Resumen' })).toHaveTextContent('Policy gap')
    await user.click(screen.getByRole('textbox', { name: 'Resumen' }))
    await user.click(screen.getByRole('button', { name: 'Bold' }))
    await user.click(screen.getByRole('button', { name: 'Italic' }))
    await user.click(screen.getByRole('button', { name: 'Bullet list' }))

    expect(document.execCommand).toHaveBeenNthCalledWith(1, 'bold')
    expect(document.execCommand).toHaveBeenNthCalledWith(2, 'italic')
    expect(document.execCommand).toHaveBeenNthCalledWith(3, 'insertUnorderedList')
  })
})
