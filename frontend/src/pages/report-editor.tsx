import { Button, Space, Typography } from 'antd'
import { forwardRef, useEffect, useImperativeHandle, useRef } from 'react'

import type { AuditReportDraft, ReportReference, ReportSections } from '../api/reports-api'
import {
  REPORT_SECTIONS,
  editorHtml,
  sanitizeReportHtml,
  type ReportSectionKey,
} from '../reports/report-html'

export interface ReportEditorHandle {
  readSections: () => ReportSections
}

interface ReportEditorProps {
  draft: AuditReportDraft
  references: ReportReference[]
}

const applyFormat = (command: 'bold' | 'italic' | 'insertUnorderedList') => {
  // These commands keep the draft to bold, italic, and lists without another package.
  if (typeof document.execCommand === 'function') {
    document.execCommand(command)
  }
}

export const ReportEditor = forwardRef<ReportEditorHandle, ReportEditorProps>(
  ({ draft, references }, ref) => {
    const nodes = useRef<Partial<Record<ReportSectionKey, HTMLDivElement | null>>>({})

    useEffect(() => {
      for (const section of REPORT_SECTIONS) {
        const node = nodes.current[section.key]
        if (node) {
          node.innerHTML = editorHtml(draft[section.key])
        }
      }
    }, [draft])

    useImperativeHandle(ref, () => ({
      readSections: () => {
        const sections = {} as ReportSections
        for (const section of REPORT_SECTIONS) {
          sections[section.key] = sanitizeReportHtml(nodes.current[section.key]?.innerHTML ?? '')
        }
        return sections
      },
    }))

    return (
      <div className="report-editor">
        <Space wrap className="report-toolbar">
          <Button
            aria-label="Bold"
            onMouseDown={(event) => event.preventDefault()}
            onClick={() => applyFormat('bold')}
          >
            Bold
          </Button>
          <Button
            aria-label="Italic"
            onMouseDown={(event) => event.preventDefault()}
            onClick={() => applyFormat('italic')}
          >
            Italic
          </Button>
          <Button
            aria-label="Bullet list"
            onMouseDown={(event) => event.preventDefault()}
            onClick={() => applyFormat('insertUnorderedList')}
          >
            Bullet list
          </Button>
        </Space>
        {REPORT_SECTIONS.map((section) => (
          <div key={section.key}>
            <Typography.Text strong>{section.label}</Typography.Text>
            <div
              role="textbox"
              aria-multiline="true"
              aria-label={section.label}
              className="report-section"
              contentEditable
              suppressContentEditableWarning
              ref={(node) => {
                nodes.current[section.key] = node
              }}
            />
          </div>
        ))}
        {references.length > 0 && (
          <>
            <Typography.Text strong>References</Typography.Text>
            <ul className="report-references">
              {references.map((reference) => (
                <li key={reference.document}>{reference.document}</li>
              ))}
            </ul>
          </>
        )}
      </div>
    )
  },
)

ReportEditor.displayName = 'ReportEditor'
