import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { listAudits, type Audit } from '../api/audits-api'
import {
  createFinding,
  listFindings,
  updateFinding,
  updateFindingStatus,
  type Finding,
} from '../api/findings-api'
import { ApiError } from '../api/http'
import { AuthContext, type AuthContextValue } from '../auth/auth-context'
import { OpenFindingsContext } from '../findings/open-findings-context'
import { FindingsPage } from './findings-page'

vi.mock('../api/audits-api', () => ({
  listAudits: vi.fn(),
}))

vi.mock('../api/findings-api', () => ({
  listFindings: vi.fn(),
  createFinding: vi.fn(),
  updateFinding: vi.fn(),
  updateFindingStatus: vi.fn(),
}))

const audit = (overrides: Partial<Audit> = {}): Audit => ({
  id: 'audit-1',
  tenant_id: 'tenant-acme',
  title: 'Line audit',
  description: null,
  audit_type: 'internal',
  status: 'planned',
  status_changed_at: null,
  planned_date: null,
  completion_date: null,
  auditor_id: null,
  created_at: '2026-10-01T12:00:00Z',
  updated_at: '2026-10-01T12:00:00Z',
  ...overrides,
})

const finding = (overrides: Partial<Finding> = {}): Finding => ({
  id: 'finding-1',
  tenant_id: 'tenant-acme',
  audit_id: 'audit-1',
  title: 'Missing record',
  description: 'The record was not filed.',
  finding_type: 'minor_nc',
  severity: 'medium',
  status: 'open',
  status_changed_at: null,
  clause_reference: '8.5.1',
  assignee_id: null,
  created_at: '2026-10-01T12:00:00Z',
  updated_at: '2026-10-01T12:00:00Z',
  ...overrides,
})

const renderPage = (role: string, refresh = vi.fn()) => {
  const value: AuthContextValue = {
    user: { email: 'ana@acme.com', tenantId: 'tenant-acme', role },
    signIn: vi.fn(),
    signOut: vi.fn(),
  }
  render(
    <AuthContext.Provider value={value}>
      <OpenFindingsContext.Provider value={{ refresh }}>
        <FindingsPage />
      </OpenFindingsContext.Provider>
    </AuthContext.Provider>,
  )
  return refresh
}

const mockFindings = (items: Finding[], total = items.length) => {
  vi.mocked(listFindings).mockResolvedValue({ items, total, skip: 0, limit: 10 })
}

const tagInRow = (title: string, label: string) => {
  const row = screen.getByText(title).closest('tr')
  expect(row).not.toBeNull()
  return within(row as HTMLElement)
    .getByText(label)
    .closest('.ant-tag')
}

describe('FindingsPage', () => {
  beforeEach(() => {
    vi.mocked(listAudits).mockReset()
    vi.mocked(listFindings).mockReset()
    vi.mocked(createFinding).mockReset()
    vi.mocked(updateFinding).mockReset()
    vi.mocked(updateFindingStatus).mockReset()
    vi.mocked(listAudits).mockResolvedValue({
      items: [audit()],
      total: 1,
      skip: 0,
      limit: 100,
    })
    mockFindings([finding()])
  })

  it('lists findings with a color badge per type', async () => {
    mockFindings([
      finding({ id: 'major', title: 'Major gap', finding_type: 'major_nc' }),
      finding({ id: 'minor', title: 'Minor gap', finding_type: 'minor_nc' }),
      finding({ id: 'obs', title: 'Noted gap', finding_type: 'observation' }),
      finding({
        id: 'idea',
        title: 'Better gap',
        finding_type: 'improvement_opportunity',
      }),
    ])
    renderPage('qa_manager')

    expect(await screen.findByRole('columnheader', { name: 'Title' })).toBeInTheDocument()
    expect(screen.getByRole('columnheader', { name: 'Type' })).toBeInTheDocument()
    expect(screen.getByRole('columnheader', { name: 'Status' })).toBeInTheDocument()
    expect(screen.getByRole('columnheader', { name: 'Audit' })).toBeInTheDocument()
    expect(screen.getByRole('columnheader', { name: 'Responsible' })).toBeInTheDocument()
    expect(screen.getByText('Major gap')).toBeInTheDocument()
    expect(screen.getAllByText('Line audit').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Unassigned').length).toBeGreaterThan(0)
    expect(tagInRow('Major gap', 'Major')).toHaveClass('ant-tag-red')
    expect(tagInRow('Minor gap', 'Minor')).toHaveClass('ant-tag-orange')
    expect(tagInRow('Noted gap', 'Observation')).toHaveClass('ant-tag-blue')
    expect(tagInRow('Better gap', 'Improvement opportunity')).toHaveClass('ant-tag-green')
    expect(screen.queryByRole('button', { name: 'New finding' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Edit' })).not.toBeInTheDocument()
    expect(listAudits).toHaveBeenCalledWith({ skip: 0, limit: 100 })
    expect(
      screen.getByText(
        'The responsible filter applies to the findings already loaded on this page. Findings are created without an assignee.',
      ),
    ).toBeInTheDocument()
  })

  it('filters by type and status through the API and by responsible on the loaded page', async () => {
    const user = userEvent.setup()
    mockFindings([
      finding({ id: 'gap-1', title: 'Unassigned gap', assignee_id: null }),
      finding({ id: 'gap-2', title: 'Assigned gap', assignee_id: 'user-9' }),
    ])
    renderPage('auditor')

    expect(await screen.findByText('Unassigned gap')).toBeInTheDocument()
    expect(screen.getByText('Assigned gap')).toBeInTheDocument()
    expect(screen.getByText('user-9')).toBeInTheDocument()
    expect(listFindings).toHaveBeenCalledTimes(1)

    await user.click(screen.getByRole('combobox', { name: 'Responsible' }))
    await user.click(await screen.findByRole('option', { name: 'Unassigned' }))

    expect(screen.queryByText('Assigned gap')).not.toBeInTheDocument()
    expect(screen.getByText('Unassigned gap')).toBeInTheDocument()
    expect(listFindings).toHaveBeenCalledTimes(1)

    await user.click(screen.getByRole('combobox', { name: 'Type' }))
    await user.click(await screen.findByRole('option', { name: 'Major' }))

    expect(listFindings).toHaveBeenLastCalledWith({
      skip: 0,
      limit: 10,
      findingType: 'major_nc',
    })

    await user.click(screen.getByRole('combobox', { name: 'Status' }))
    await user.click(await screen.findByRole('option', { name: 'Open' }))

    expect(listFindings).toHaveBeenLastCalledWith({
      skip: 0,
      limit: 10,
      findingType: 'major_nc',
      status: 'open',
    })
  })

  it('explains when the responsible filter hides the loaded page', async () => {
    const user = userEvent.setup()
    mockFindings([finding({ title: 'Assigned gap', assignee_id: 'user-9' })])
    renderPage('qa_manager')

    expect(await screen.findByText('Assigned gap')).toBeInTheDocument()
    await user.click(screen.getByRole('combobox', { name: 'Responsible' }))
    await user.click(await screen.findByRole('option', { name: 'Unassigned' }))

    expect(
      screen.getByText('No findings on this page match the responsible filter.'),
    ).toBeInTheDocument()
  })

  it('opens a detail timeline with the last status change only', async () => {
    mockFindings([finding({ status_changed_at: '2026-10-21T17:40:00Z' })])
    renderPage('auditee')

    await userEvent.click(await screen.findByRole('button', { name: 'View' }))

    const dialog = await screen.findByRole('dialog')
    expect(within(dialog).getByText('Open', { exact: true })).toBeInTheDocument()
    expect(within(dialog).getByText('In progress', { exact: true })).toBeInTheDocument()
    expect(within(dialog).getByText('Resolved', { exact: true })).toBeInTheDocument()
    expect(within(dialog).getByText('Verified', { exact: true })).toBeInTheDocument()
    expect(within(dialog).getByText('Closed', { exact: true })).toBeInTheDocument()
    expect(within(dialog).getByText('Last status change: 2026-10-21 17:40 UTC')).toBeInTheDocument()
    expect(within(dialog).queryByRole('button', { name: 'Edit' })).not.toBeInTheDocument()
    expect(within(dialog).queryByRole('button', { name: /Move to/ })).not.toBeInTheDocument()
    expect(within(dialog).queryByRole('button', { name: /Return to/ })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'New finding' })).not.toBeInTheDocument()
  })

  it('lets an auditor create a finding on the selected audit', async () => {
    const user = userEvent.setup()
    const refresh = vi.fn()
    vi.mocked(listFindings).mockReset()
    vi.mocked(listFindings)
      .mockResolvedValue({
        items: [finding({ title: 'Line gap', finding_type: 'major_nc' })],
        total: 1,
        skip: 0,
        limit: 10,
      })
      .mockResolvedValueOnce({ items: [], total: 0, skip: 0, limit: 10 })
    vi.mocked(createFinding).mockResolvedValue(
      finding({ title: 'Line gap', finding_type: 'major_nc' }),
    )
    renderPage('auditor', refresh)

    expect(await screen.findByText('No findings yet.')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'New finding' }))
    const dialog = await screen.findByRole('dialog')
    await user.click(within(dialog).getByRole('combobox', { name: 'Audit' }))
    await user.click(await screen.findByRole('option', { name: 'Line audit' }))
    await user.click(within(dialog).getByRole('combobox', { name: 'Type' }))
    await user.click(await screen.findByRole('option', { name: 'Major' }))
    await user.type(within(dialog).getByLabelText('Title'), 'Line gap')
    await user.click(within(dialog).getByRole('button', { name: 'Create finding' }))

    expect(createFinding).toHaveBeenCalledWith('audit-1', {
      title: 'Line gap',
      description: null,
      findingType: 'major_nc',
      severity: 'medium',
      clauseReference: null,
    })
    expect(refresh).toHaveBeenCalledOnce()
    expect(await screen.findByText('Line gap')).toBeInTheDocument()
  })

  it('lets an admin move an open finding to in progress', async () => {
    const user = userEvent.setup()
    const refresh = renderPage('admin')

    await user.click(await screen.findByRole('button', { name: 'View' }))
    const dialog = await screen.findByRole('dialog')
    expect(within(dialog).getByText('No status change recorded yet.')).toBeInTheDocument()
    expect(
      within(dialog).queryByRole('button', { name: 'Return to in progress' }),
    ).not.toBeInTheDocument()
    vi.mocked(updateFindingStatus).mockResolvedValue(finding({ status: 'in_progress' }))
    await user.click(within(dialog).getByRole('button', { name: 'Move to in progress' }))

    expect(updateFindingStatus).toHaveBeenCalledWith('finding-1', 'in_progress')
    expect(refresh).toHaveBeenCalledOnce()
    expect(within(screen.getByRole('table')).getByText('In progress')).toBeInTheDocument()
  })

  it('shows the status error from the API', async () => {
    const user = userEvent.setup()
    vi.mocked(updateFindingStatus).mockRejectedValue(
      new ApiError("You cannot change this finding's status", 403),
    )
    renderPage('admin')

    await user.click(await screen.findByRole('button', { name: 'View' }))
    const dialog = await screen.findByRole('dialog')
    await user.click(within(dialog).getByRole('button', { name: 'Move to in progress' }))

    expect(
      await within(dialog).findByText("You cannot change this finding's status"),
    ).toBeInTheDocument()
  })

  it('lets an auditor send a resolved finding back to in progress', async () => {
    const user = userEvent.setup()
    mockFindings([finding({ status: 'resolved' })])
    renderPage('auditor')

    await user.click(await screen.findByRole('button', { name: 'View' }))
    const dialog = await screen.findByRole('dialog')
    expect(within(dialog).getByRole('button', { name: 'Move to verified' })).toBeInTheDocument()
    vi.mocked(updateFindingStatus).mockResolvedValue(finding({ status: 'in_progress' }))
    await user.click(within(dialog).getByRole('button', { name: 'Return to in progress' }))

    expect(updateFindingStatus).toHaveBeenCalledWith('finding-1', 'in_progress')
    expect(within(dialog).queryByRole('button', { name: 'Move to closed' })).not.toBeInTheDocument()
  })

  it('lets a lead auditor edit the descriptive fields', async () => {
    const user = userEvent.setup()
    const refresh = renderPage('lead_auditor')
    vi.mocked(updateFinding).mockResolvedValue(finding({ title: 'Renamed finding' }))

    await user.click(await screen.findByRole('button', { name: 'Edit' }))
    const title = screen.getByLabelText('Title')
    await user.clear(title)
    await user.type(title, 'Renamed finding')
    await user.click(screen.getByRole('button', { name: 'Save changes' }))

    expect(updateFinding).toHaveBeenCalledWith('finding-1', {
      title: 'Renamed finding',
      description: 'The record was not filed.',
      findingType: 'minor_nc',
      severity: 'medium',
      clauseReference: '8.5.1',
    })
    expect(await screen.findByText('Renamed finding')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'New finding' })).toBeInTheDocument()
    expect(refresh).not.toHaveBeenCalled()
  })

  it('shows the list error from the API', async () => {
    vi.mocked(listFindings).mockRejectedValue(
      new ApiError('Could not reach the API. Check that the backend is running.', 0),
    )
    renderPage('auditor')

    expect(
      await screen.findByText('Could not reach the API. Check that the backend is running.'),
    ).toBeInTheDocument()
  })
})
