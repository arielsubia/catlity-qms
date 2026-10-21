import { describe, expect, it } from 'vitest'

import type { Audit } from '../api/audits-api'
import { auditorLabel, filterByPlannedDate, formatStatusChangedAt, nextStatus } from './audit-view'

const audit = (plannedDate: string | null, title: string): Audit => ({
  id: title,
  tenant_id: 'tenant-acme',
  title,
  description: null,
  audit_type: 'internal',
  status: 'planned',
  status_changed_at: null,
  planned_date: plannedDate,
  completion_date: null,
  auditor_id: null,
  created_at: '2026-10-01T00:00:00Z',
  updated_at: '2026-10-01T00:00:00Z',
})

describe('audit view helpers', () => {
  it('keeps the next status inside the forward path', () => {
    expect(nextStatus('planned')).toBe('in_progress')
    expect(nextStatus('completed')).toBe('closed')
    expect(nextStatus('closed')).toBeNull()
  })

  it('filters the loaded page by planned date', () => {
    const rows = [audit('2026-01-15', 'January'), audit('2026-06-01', 'June'), audit(null, 'Open')]

    expect(filterByPlannedDate(rows, '2026-05-01', '').map((row) => row.title)).toEqual(['June'])
    expect(filterByPlannedDate(rows, '', '2026-02-01').map((row) => row.title)).toEqual(['January'])
    expect(filterByPlannedDate(rows, '', '').map((row) => row.title)).toEqual([
      'January',
      'June',
      'Open',
    ])
  })

  it('shows a name only when the auditor list contains that id', () => {
    const roster = [
      { id: 'user-1', full_name: 'Ada Lovelace', email: 'ada@acme.com', role: 'auditor' },
    ]

    expect(auditorLabel(null, roster)).toBe('Unassigned')
    expect(auditorLabel('user-1', roster)).toBe('Ada Lovelace')
    expect(auditorLabel('user-9', roster)).toBe('user-9')
    expect(auditorLabel('user-1', null)).toBe('user-1')
  })

  it('formats the last status change in UTC', () => {
    expect(formatStatusChangedAt('2026-10-21T17:40:00Z')).toBe('2026-10-21 17:40 UTC')
  })
})
