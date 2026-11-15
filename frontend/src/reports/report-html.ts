// The print view inserts this HTML. Only the marks the toolbar creates are kept.

const ALLOWED = new Set(['p', 'br', 'strong', 'em', 'b', 'i', 'ul', 'ol', 'li'])
const DROPPED = new Set(['script', 'style'])

export const REPORT_SECTIONS = [
  { key: 'resumen', label: 'Resumen' },
  { key: 'hallazgos', label: 'Hallazgos' },
  { key: 'conclusiones', label: 'Conclusiones' },
  { key: 'recomendaciones', label: 'Recomendaciones' },
] as const

export type ReportSectionKey = (typeof REPORT_SECTIONS)[number]['key']

const escapeText = (value: string): string =>
  value.replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;')

const cleanNode = (node: Node): string => {
  if (node.nodeType === Node.TEXT_NODE) {
    return escapeText(node.textContent ?? '')
  }
  if (node.nodeType !== Node.ELEMENT_NODE) {
    return ''
  }
  const element = node as HTMLElement
  const tag = element.tagName.toLowerCase()
  if (DROPPED.has(tag)) {
    return ''
  }
  const inner = Array.from(element.childNodes).map(cleanNode).join('')
  if (tag === 'br') {
    return '<br>'
  }
  if (tag === 'div') {
    return `<p>${inner}</p>`
  }
  if (ALLOWED.has(tag)) {
    return `<${tag}>${inner}</${tag}>`
  }
  return inner
}

export const sanitizeReportHtml = (value: string): string => {
  const template = document.createElement('template')
  template.innerHTML = value
  return Array.from(template.content.childNodes).map(cleanNode).join('')
}

export const reportPlainText = (value: string): string =>
  sanitizeReportHtml(value)
    .replaceAll(/<[^>]+>/g, ' ')
    .replaceAll('&nbsp;', ' ')
    .replaceAll('&amp;', '&')
    .replaceAll('&lt;', '<')
    .replaceAll('&gt;', '>')
    .replaceAll(/\s+/g, ' ')
    .trim()

export const editorHtml = (value: string): string => {
  const cleaned = sanitizeReportHtml(value)
  if (/<[a-z]/i.test(cleaned)) {
    return cleaned
  }
  return cleaned.replaceAll('\n', '<br>')
}

export const sectionsHaveText = (sections: Record<ReportSectionKey, string>): boolean =>
  REPORT_SECTIONS.every((section) => reportPlainText(sections[section.key]) !== '')
