import type { ExtractedField, ValidationIssue, ValidationResult } from './types.js'

const RULE_VERSION = '2026.09.3'
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

export function validateInvoice(invoice: Record<string, unknown>, confidenceThreshold: number, extractionWarnings: string[] = []): ValidationResult {
  const issues: ValidationIssue[] = []
  const required = [
    ['header.invoiceNumber', 'Invoice number'],
    ['header.invoiceDate', 'Invoice date'],
    ['header.currency', 'Currency'],
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
  if (!lines.length) issue(issues, '/lineItems', 'MISSING_LINE_ITEMS', 'No line items were extracted; compare with the source invoice', 'WARN')
  for (const [index, line] of lines.entries()) {
    const record = typeof line === 'object' && line !== null ? line as Record<string, unknown> : {}
    if (numericValue(isField(record.amount) ? record.amount : undefined) === undefined) {
      issue(issues, `/lineItems/${index}/amount`, 'INVALID_LINE_AMOUNT', 'A numeric line amount is required for reconciliation', 'BLOCK')
    }
    if (!isField(record.description) || !String(record.description.value ?? '').trim()) {
      issue(issues, `/lineItems/${index}/description`, 'MISSING_LINE_DESCRIPTION', 'Line description is missing', 'WARN')
    }
    if (isField(record.unitPrice) && record.unitPrice.value != null &&
        (!isField(record.quantity) || record.quantity.value == null)) {
      issue(issues, `/lineItems/${index}/unitPrice`, 'PRICE_WITHOUT_QUANTITY', 'Unit price has no quantity; verify that a line amount was not misclassified', 'WARN')
    }
    const deliveryDate = isField(record.deliveryDate) ? record.deliveryDate.value : undefined
    const deliveryLocation = isField(record.deliveryLocation) ? record.deliveryLocation.value : undefined
    const rowCurrency = isField(record.currency) ? record.currency.value : undefined
    if ((deliveryDate != null || deliveryLocation != null || rowCurrency != null) &&
        (deliveryDate == null || deliveryLocation == null || rowCurrency == null)) {
      issue(issues, `/lineItems/${index}`, 'INCOMPLETE_DELIVERY_ROW', 'Delivery date, location and row currency must be extracted together', 'WARN')
    }
  }
  if (numericValue(fieldAt(invoice, 'amounts.total')) === undefined) {
    issue(issues, '/amounts/total', 'INVALID_AMOUNT', 'Total must be numeric', 'BLOCK')
  }
  for (const warning of extractionWarnings) {
    issue(issues, '/', 'EXTRACTION_WARNING', warning, 'WARN')
  }
  const supplier = String(fieldAt(invoice, 'vendor.name')?.value ?? '').trim().toLowerCase()
  const buyer = String(fieldAt(invoice, 'billTo.entity')?.value ?? '').trim().toLowerCase()
  if (supplier && supplier === buyer) {
    issue(issues, '/billTo/entity', 'PARTY_ROLE_AMBIGUOUS', 'Supplier and buyer are identical; verify their roles', 'WARN')
  }
  const accountingReference = String(fieldAt(invoice, 'billTo.accountingReference')?.value ?? '').trim().toLowerCase()
  if (buyer && accountingReference === buyer) {
    issue(issues, '/billTo/accountingReference', 'REFERENCE_ROLE_AMBIGUOUS', 'Customer name was also mapped as an accounting reference; verify source', 'WARN')
  }
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
