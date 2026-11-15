import { describe, expect, it } from 'vitest'

import { editorHtml, reportPlainText, sanitizeReportHtml } from './report-html'

describe('report html', () => {
  it('keeps bold and turns a plain newline into a break', () => {
    expect(sanitizeReportHtml('<b onclick="x">Listo</b>')).toBe('<b>Listo</b>')
    expect(editorHtml('A\nB')).toBe('A<br>B')
    expect(reportPlainText('<b>Listo</b>')).toBe('Listo')
  })

  it('drops script and an empty section', () => {
    expect(sanitizeReportHtml('<script>alert(1)</script><div>Listo</div>')).toBe('<p>Listo</p>')
    expect(reportPlainText('<script>alert(1)</script>')).toBe('')
    expect(reportPlainText('   ')).toBe('')
  })
})
