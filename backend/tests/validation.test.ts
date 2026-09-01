import { describe, expect, it } from 'vitest'

import { overallConfidence } from '../src/domain/confidence.js'
import { validateInvoice } from '../src/domain/validation.js'

const field = (value: unknown, confidence = 0.99) => ({ value, confidence, source: 'test' })

function validInvoice() {
  return {
    header: {
      invoiceNumber: field('INV-100'),
      invoiceDate: field(new Date().toISOString().slice(0, 10)),
      currency: field('USD'),
    },
    vendor: { name: field('Synthetic Vendor') },
    amounts: { total: field(109), tax: field(9), shipping: field(0), discount: field(0) },
    lineItems: [{ lineNumber: field('1'), description: field('Service'), amount: field(100) }],
  }
}

describe('invoice validation', () => {
  it('accepts a reconciled high-confidence invoice', () => {
    const result = validateInvoice(validInvoice(), 0.7)
    expect(result.reviewRequired).toBe(false)
    expect(result.issues).toEqual([])
  })

  it('routes missing, low-confidence and unreconciled fields to review', () => {
    const invoice = validInvoice()
    invoice.header.invoiceNumber = field(null)
    invoice.amounts.total = field(500, 0.4)
    const result = validateInvoice(invoice, 0.7)
    expect(result.reviewRequired).toBe(true)
    expect(result.issues.map((entry) => entry.code)).toEqual(expect.arrayContaining([
      'MISSING_REQUIRED', 'LOW_CONFIDENCE', 'AMOUNT_MISMATCH',
    ]))
  })

  it('computes mean confidence across nested scalar fields', () => {
    expect(overallConfidence({ one: field('a', 1), nested: { two: field('b', 0.5) } })).toBe(0.75)
  })
})
