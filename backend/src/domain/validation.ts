import type { ExtractedField, ValidationIssue, ValidationResult } from './types.js'

const RULE_VERSION = '2026.09.1'
const CURRENCY = /^[A-Z]{3}$/
const ISO_DATE = /^\d{4}-\d{2}-\d{2}$/

function isField(value: unknown): value is ExtractedField {
  return typeof value === 'object' && value !== null && 'value' in value && 'confidence' in value
}

export function fieldAt(invoice: Record<string, unknown>, path: string): ExtractedField | undefined {
  let value: unknown = invoice
  for (const segment of path.split('.')) {
    if (typeof value !== 'object' || value === null || Array.isArray(value)) return undefined
    value = (value as Record<string, unknown>)[segment]
  }
  return isField(value) ? value : undefined
}

function issue(issues: ValidationIssue[], field: string, code: string, message: string, severity: ValidationIssue['severity']) {
  issues.push({ field, code, message, severity })
}

function walkConfidence(value: unknown, path: string, threshold: number, issues: ValidationIssue[]): void {
  if (isField(value)) {
    if (value.value !== null && value.value !== '' && Number(value.confidence) < threshold) {
      issue(issues, path, 'LOW_CONFIDENCE', `Field confidence is below ${threshold}`, 'WARN')
    }
    return
  }
  if (Array.isArray(value)) {
    value.forEach((entry, index) => walkConfidence(entry, `${path}/${index}`, threshold, issues))
    return
  }
  if (typeof value === 'object' && value !== null) {
    for (const [key, entry] of Object.entries(value)) walkConfidence(entry, `${path}/${key}`, threshold, issues)
  }
}

function numericValue(field: ExtractedField | undefined): number | undefined {
  if (!field || field.value === null || field.value === '') return undefined
  const value = Number(field.value)
  return Number.isFinite(value) ? value : undefined
}

export function validateInvoice(invoice: Record<string, unknown>, confidenceThreshold: number): ValidationResult {
  const issues: ValidationIssue[] = []
  const required = [
    ['header.invoiceNumber', 'Invoice number'],
    ['header.invoiceDate', 'Invoice date'],
    ['vendor.name', 'Vendor name'],
    ['amounts.total', 'Total amount'],
  ] as const
  for (const [path, label] of required) {
    const value = fieldAt(invoice, path)?.value
    if (value === null || value === undefined || String(value).trim() === '') {
      issue(issues, `/${path.replaceAll('.', '/')}`, 'MISSING_REQUIRED', `${label} is required`, 'BLOCK')
    }
  }

  const currency = fieldAt(invoice, 'header.currency')?.value
  if (currency !== null && currency !== undefined && !CURRENCY.test(String(currency).toUpperCase())) {
    issue(issues, '/header/currency', 'INVALID_CURRENCY', 'Currency must use an ISO 4217 code', 'BLOCK')
  }

  const invoiceDate = fieldAt(invoice, 'header.invoiceDate')?.value
  if (invoiceDate !== null && invoiceDate !== undefined && invoiceDate !== '') {
    const text = String(invoiceDate)
    const timestamp = Date.parse(`${text}T00:00:00Z`)
    if (!ISO_DATE.test(text) || Number.isNaN(timestamp)) {
      issue(issues, '/header/invoiceDate', 'INVALID_DATE', 'Invoice date must use ISO format YYYY-MM-DD', 'BLOCK')
    } else {
      const today = new Date()
      const oldest = new Date(today)
      oldest.setUTCFullYear(oldest.getUTCFullYear() - 1)
      if (timestamp > today.getTime() || timestamp < oldest.getTime()) {
        issue(issues, '/header/invoiceDate', 'DATE_SANITY', 'Invoice date is outside the allowed range', 'WARN')
      }
    }
  }

  const lines = Array.isArray(invoice.lineItems) ? invoice.lineItems : []
  if (lines.length) {
    const lineTotal = lines.reduce((sum, line) => {
      if (typeof line !== 'object' || line === null) return sum
      return sum + (numericValue(isField((line as Record<string, unknown>).amount) ? (line as Record<string, unknown>).amount as ExtractedField : undefined) ?? 0)
    }, 0)
    const tax = numericValue(fieldAt(invoice, 'amounts.tax')) ?? 0
    const shipping = numericValue(fieldAt(invoice, 'amounts.shipping')) ?? 0
    const discount = numericValue(fieldAt(invoice, 'amounts.discount')) ?? 0
    const total = numericValue(fieldAt(invoice, 'amounts.total'))
    if (total !== undefined && Math.abs(lineTotal + tax + shipping - discount - total) > 0.02) {
      issue(issues, '/amounts/total', 'AMOUNT_MISMATCH', 'Line amounts, tax, shipping and discount do not reconcile to total', 'BLOCK')
    }
  }

  walkConfidence(invoice, '', confidenceThreshold, issues)
  return { reviewRequired: issues.length > 0, issues, ruleVersion: RULE_VERSION }
}
