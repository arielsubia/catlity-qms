import { describe, expect, it } from 'vitest'

import type { Finding } from '../api/findings-api'
import {
  assigneeLabel,
  auditLabel,
  filterByResponsible,
  statusActions,
  typeColor,
} from './finding-view'

const finding = (assigneeId: string | null, title: string): Finding => ({
  id: title,
  tenant_id: 'tenant-acme',
  audit_id: 'audit-1',
  title,
  description: null,
  finding_type: 'minor_nc',
  severity: 'medium',
  status: 'open',
  status_changed_at: null,
  clause_reference: null,
  assignee_id: assigneeId,
  created_at: '2026-10-01T00:00:00Z',
  updated_at: '2026-10-01T00:00:00Z',
})

describe('finding view helpers', () => {
  it('colors each finding type', () => {
    expect(typeColor('major_nc')).toBe('red')
    expect(typeColor('minor_nc')).toBe('orange')
    expect(typeColor('observation')).toBe('blue')
    expect(typeColor('improvement_opportunity')).toBe('green')
  })

  it('keeps an unknown audit id and an empty assignee visible', () => {
    expect(assigneeLabel(null)).toBe('Unassigned')
    expect(assigneeLabel('user-9')).toBe('user-9')
    expect(auditLabel('audit-1', [{ id: 'audit-1', title: 'Line audit' }])).toBe('Line audit')
    expect(auditLabel('audit-9', [])).toBe('audit-9')
  })

  it('filters the loaded page to findings without an assignee', () => {
    const rows = [finding(null, 'Open gap'), finding('user-9', 'Assigned gap')]

    expect(filterByResponsible(rows, 'all').map((row) => row.title)).toEqual([
      'Open gap',
      'Assigned gap',
    ])
    expect(filterByResponsible(rows, 'unassigned').map((row) => row.title)).toEqual(['Open gap'])
  })

  it('offers status actions from the role and the current status', () => {
    expect(statusActions('admin', 'open').map((action) => action.label)).toEqual([
      'Move to in progress',
    ])
    expect(statusActions('admin', 'in_progress').map((action) => action.status)).toEqual([
      'resolved',
    ])
    expect(statusActions('admin', 'resolved').map((action) => action.label)).toEqual([
      'Move to verified',
      'Return to in progress',
    ])
    expect(statusActions('auditor', 'resolved').map((action) => action.status)).toEqual([
      'verified',
      'in_progress',
    ])
    expect(statusActions('lead_auditor', 'verified').map((action) => action.status)).toEqual([
      'closed',
    ])
    expect(statusActions('auditor', 'open')).toEqual([])
    expect(statusActions('auditee', 'in_progress')).toEqual([])
    expect(statusActions('qa_manager', 'resolved')).toEqual([])
    expect(statusActions('admin', 'closed')).toEqual([])
  })
})
