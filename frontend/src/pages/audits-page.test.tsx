import { fireEvent, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import {
  assignAuditor,
  createAudit,
  getAudit,
  listAuditors,
  listAudits,
  updateAudit,
  updateAuditStatus,
  type Audit,
} from '../api/audits-api'
import { ApiError } from '../api/http'
import { AuthContext, type AuthContextValue } from '../auth/auth-context'

import { AuditsPage } from './audits-page'

vi.mock('../api/audits-api', () => ({
  listAudits: vi.fn(),
  listAuditors: vi.fn(),
  getAudit: vi.fn(),
  createAudit: vi.fn(),
  updateAudit: vi.fn(),
  assignAuditor: vi.fn(),
  updateAuditStatus: vi.fn(),
}))

const audit = (overrides: Partial<Audit> = {}): Audit => ({
  id: 'audit-1',
  tenant_id: 'tenant-acme',
  title: 'Line audit',
  description: 'Check the line',
  audit_type: 'internal',
  status: 'planned',
  status_changed_at: null,
  planned_date: '2026-06-01',
  completion_date: null,
  auditor_id: 'user-1',
  created_at: '2026-10-01T12:00:00Z',
  updated_at: '2026-10-01T12:00:00Z',
  ...overrides,
})

const roster = [{ id: 'user-1', full_name: 'Ada Lovelace', email: 'ada@acme.com', role: 'auditor' }]

const renderPage = (role: string) => {
  const value: AuthContextValue = {
    user: { email: 'ana@acme.com', tenantId: 'tenant-acme', role },
    signIn: vi.fn(),
    signOut: vi.fn(),
  }
  render(
    <AuthContext.Provider value={value}>
      <AuditsPage />
    </AuthContext.Provider>,
  )
}

const mockAudits = (items: Audit[], total = items.length) => {
  vi.mocked(listAudits).mockResolvedValue({ items, total, skip: 0, limit: 10 })
  vi.mocked(getAudit).mockImplementation(async (id: string) => {
    const found = items.find((item) => item.id === id)
    if (!found) {
      throw new ApiError('Audit not found', 404)
    }
    return found
  })
}

describe('AuditsPage', () => {
  beforeEach(() => {
    vi.mocked(listAudits).mockReset()
    vi.mocked(listAuditors).mockReset()
    vi.mocked(getAudit).mockReset()
    vi.mocked(createAudit).mockReset()
    vi.mocked(updateAudit).mockReset()
    vi.mocked(assignAuditor).mockReset()
    vi.mocked(updateAuditStatus).mockReset()
    vi.mocked(listAuditors).mockResolvedValue(roster)
    mockAudits([audit()])
  })

  it('lists name, status, auditor id, date, and actions', async () => {
    renderPage('qa_manager')

    expect(await screen.findByRole('columnheader', { name: 'Name' })).toBeInTheDocument()
    expect(screen.getByRole('columnheader', { name: 'Status' })).toBeInTheDocument()
    expect(screen.getByRole('columnheader', { name: 'Auditor' })).toBeInTheDocument()
    expect(screen.getByRole('columnheader', { name: 'Date' })).toBeInTheDocument()
    expect(screen.getByRole('columnheader', { name: 'Actions' })).toBeInTheDocument()
    expect(screen.getByText('Line audit')).toBeInTheDocument()
    expect(screen.getByText('Planned')).toBeInTheDocument()
    expect(screen.getByText('user-1')).toBeInTheDocument()
    expect(screen.getByText('2026-06-01')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'View' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'New audit' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Edit' })).not.toBeInTheDocument()
    expect(listAuditors).not.toHaveBeenCalled()
  })

  it('shows the auditor name when the role can load the roster', async () => {
    renderPage('admin')

    expect(await screen.findByText('Ada Lovelace')).toBeInTheDocument()
    expect(screen.queryByText('user-1')).not.toBeInTheDocument()
    expect(listAuditors).toHaveBeenCalledOnce()
  })

  it('filters by status through the API and by date on the loaded page', async () => {
    const user = userEvent.setup()
    mockAudits([
      audit({ id: 'jan', title: 'January audit', planned_date: '2026-01-15' }),
      audit({ id: 'jun', title: 'June audit', planned_date: '2026-06-01' }),
    ])
    renderPage('auditor')

    expect(await screen.findByText('January audit')).toBeInTheDocument()
    expect(screen.getByText('June audit')).toBeInTheDocument()

    fireEvent.change(screen.getByLabelText('From'), { target: { value: '2026-05-01' } })

    expect(screen.queryByText('January audit')).not.toBeInTheDocument()
    expect(screen.getByText('June audit')).toBeInTheDocument()
    expect(listAudits).toHaveBeenCalledTimes(1)

    await user.click(screen.getByRole('combobox', { name: 'Status' }))
    await user.click(await screen.findByRole('option', { name: 'Planned' }))

    expect(listAudits).toHaveBeenLastCalledWith({ skip: 0, limit: 10, status: 'planned' })
  })

  it('opens a detail timeline with the last status change only', async () => {
    const row = audit({ status_changed_at: '2026-10-21T17:40:00Z' })
    mockAudits([row])
    renderPage('qa_manager')

    await userEvent.click(await screen.findByRole('button', { name: 'View' }))

    const dialog = await screen.findByRole('dialog')
    expect(within(dialog).getByText('Planned', { exact: true })).toBeInTheDocument()
    expect(within(dialog).getByText('In progress', { exact: true })).toBeInTheDocument()
    expect(within(dialog).getByText('Completed', { exact: true })).toBeInTheDocument()
    expect(within(dialog).getByText('Closed', { exact: true })).toBeInTheDocument()
    expect(within(dialog).getByText('Last status change: 2026-10-21 17:40 UTC')).toBeInTheDocument()
    expect(within(dialog).queryByRole('button', { name: 'Edit' })).not.toBeInTheDocument()
    expect(within(dialog).queryByRole('button', { name: /Move to/ })).not.toBeInTheDocument()
    expect(within(dialog).queryByRole('button', { name: 'Assign auditor' })).not.toBeInTheDocument()
  })

  it('lets an auditor create an audit and shows the API error when status is forbidden', async () => {
    const user = userEvent.setup()
    vi.mocked(listAudits)
      .mockResolvedValueOnce({ items: [], total: 0, skip: 0, limit: 10 })
      .mockResolvedValueOnce({
        items: [audit({ title: 'Line audit' })],
        total: 1,
        skip: 0,
        limit: 10,
      })
    vi.mocked(createAudit).mockResolvedValue(audit({ title: 'Line audit' }))
    renderPage('auditor')

    await user.click(await screen.findByRole('button', { name: 'New audit' }))
    await user.type(screen.getByLabelText('Name'), 'Line audit')
    await user.type(screen.getByLabelText('Description'), 'Check the line')
    await user.click(screen.getByRole('button', { name: 'Create audit' }))

    expect(createAudit).toHaveBeenCalledWith({
      title: 'Line audit',
      description: 'Check the line',
      auditType: 'internal',
      plannedDate: null,
    })
    expect(await screen.findByText('Line audit')).toBeInTheDocument()

    vi.mocked(updateAuditStatus).mockRejectedValue(
      new ApiError('Only the assigned auditor can change this audit', 403),
    )
    await user.click(screen.getByRole('button', { name: 'View' }))
    const dialog = await screen.findByRole('dialog')
    await user.click(within(dialog).getByRole('button', { name: 'Move to in progress' }))

    expect(
      await within(dialog).findByText('Only the assigned auditor can change this audit'),
    ).toBeInTheDocument()
    expect(within(dialog).queryByRole('button', { name: 'Assign auditor' })).not.toBeInTheDocument()
  })

  it('lets a lead auditor assign an auditor and hides the status change', async () => {
    const user = userEvent.setup()
    mockAudits([audit({ auditor_id: null })])
    renderPage('lead_auditor')

    expect(await screen.findByText('Unassigned')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'View' }))

    const dialog = await screen.findByRole('dialog')
    expect(within(dialog).queryByRole('button', { name: /Move to/ })).not.toBeInTheDocument()
    await user.click(within(dialog).getByRole('combobox', { name: 'Auditor' }))
    await user.click(await screen.findByRole('option', { name: 'Ada Lovelace' }))
    vi.mocked(assignAuditor).mockResolvedValue(audit({ auditor_id: 'user-1' }))
    await user.click(within(dialog).getByRole('button', { name: 'Assign auditor' }))

    expect(assignAuditor).toHaveBeenCalledWith('audit-1', 'user-1')
    expect(within(screen.getByRole('table')).getByText('Ada Lovelace')).toBeInTheDocument()
  })

  it('lets an auditee edit the descriptive fields', async () => {
    const user = userEvent.setup()
    vi.mocked(updateAudit).mockResolvedValue(audit({ title: 'Renamed audit' }))
    renderPage('auditee')

    await user.click(await screen.findByRole('button', { name: 'Edit' }))
    const name = screen.getByLabelText('Name')
    await user.clear(name)
    await user.type(name, 'Renamed audit')
    await user.click(screen.getByRole('button', { name: 'Save changes' }))

    expect(updateAudit).toHaveBeenCalledWith('audit-1', {
      title: 'Renamed audit',
      description: 'Check the line',
      auditType: 'internal',
      plannedDate: '2026-06-01',
    })
    expect(await screen.findByText('Renamed audit')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'New audit' })).not.toBeInTheDocument()
  })

  it('shows the list error from the API', async () => {
    vi.mocked(listAudits).mockRejectedValue(
      new ApiError('Could not reach the API. Check that the backend is running.', 0),
    )
    renderPage('auditor')

    expect(
      await screen.findByText('Could not reach the API. Check that the backend is running.'),
    ).toBeInTheDocument()
  })
})
