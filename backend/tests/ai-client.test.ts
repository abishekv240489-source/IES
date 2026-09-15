import { mkdtemp, rm, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { loadConfig } from '../src/config.js'
import { extractInvoice } from '../src/services/processor/ai-client.js'

let mockGenerateContent = vi.fn()

vi.mock('@google/genai', () => {
  return {
    GoogleGenAI: class MockGoogleGenAI {
      models: any;
      constructor() {
        this.models = {
          generateContent: (...args: any[]) => mockGenerateContent(...args)
        };
      }
    },
    Type: { OBJECT: 'OBJECT', STRING: 'STRING', NUMBER: 'NUMBER', ARRAY: 'ARRAY' }
  }
})

afterEach(() => {
  vi.unstubAllGlobals()
  vi.clearAllMocks()
  mockGenerateContent.mockReset()
})

async function withInput(run: (input: { jobId: string; path: string; originalFilename: string; contentType: string }) => Promise<void>) {
  const directory = await mkdtemp(join(tmpdir(), 'ies-ai-client-test-'))
  try {
    const path = join(directory, 'synthetic.pdf')
    await writeFile(path, '%PDF-synthetic-test')
    await run({ jobId: 'synthetic-job', path, originalFilename: 'synthetic.pdf', contentType: 'application/pdf' })
  } finally {
    await rm(directory, { recursive: true, force: true })
  }
}

describe('AI client failure classification', () => {
  it('distinguishes worker backpressure from extraction failures', async () => {
    mockGenerateContent.mockRejectedValue(new Error('503 Service Unavailable'))

    await withInput(async (input) => {
      await expect(extractInvoice(loadConfig({}), input)).rejects.toThrow('AI_WORKER_BUSY')
    })
  })

  it('reports pipeline timeouts explicitly', async () => {
    mockGenerateContent.mockImplementation(() => new Promise((resolve) => setTimeout(resolve, 1500)))

    await withInput(async (input) => {
      await expect(extractInvoice(loadConfig({ IES_AI_TIMEOUT_MS: '1000' }), input)).rejects.toThrow('AI_WORKER_TIMEOUT')
    })
  })

  it('parses valid AI extraction response', async () => {
    const mockInvoiceData = {
      header: {
        invoiceNumber: { value: 'INV-123', confidence: 0.99 },
        invoiceDate: { value: '2023-01-01', confidence: 0.99 },
        currency: { value: 'USD', confidence: 0.99 }
      },
      vendor: {
        vendorName: { value: 'Vendor Inc', confidence: 0.99 }
      },
      amounts: {
        total: { value: '100.00', confidence: 0.99 }
      },
      lineItems: []
    }
    mockGenerateContent.mockResolvedValue({
      text: JSON.stringify(mockInvoiceData)
    })

    await withInput(async (input) => {
      const result = await extractInvoice(loadConfig({}), input)
      expect(result.invoice).toEqual(mockInvoiceData)
      expect(result.document_id).toEqual('synthetic-job')
    })
  })
})
