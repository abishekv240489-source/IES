import { mkdtemp, readdir, readFile, rm } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { resolve } from 'node:path'

import { PGlite } from '@electric-sql/pglite'
import { afterAll, beforeAll, describe, expect, it } from 'vitest'

import { loadConfig } from '../src/config.js'
import type { Database } from '../src/db/pool.js'
import { buildApi } from '../src/services/api/app.js'
import { InvoiceProcessor } from '../src/services/processor/processor.js'

class PGlitePoolAdapter {
  constructor(private readonly database: PGlite) {}

  async query<T extends Record<string, unknown>>(sql: string, parameters?: unknown[]) {
    const result = await this.database.query<T>(sql, parameters)
    return { ...result, rowCount: result.affectedRows ?? result.rows.length }
  }

  async connect() {
    return { query: this.query.bind(this), release: () => undefined }
  }

  async end() {
    await this.database.close()
  }
}

function multipart(filename: string, content: Buffer) {
  const boundary = 'IES-TEST-BOUNDARY'
  return {
    contentType: `multipart/form-data; boundary=${boundary}`,
    body: Buffer.concat([
      Buffer.from(`--${boundary}\r\nContent-Disposition: form-data; name="files"; filename="${filename}"\r\nContent-Type: application/octet-stream\r\n\r\n`),
      content,
      Buffer.from(`\r\n--${boundary}--\r\n`),
    ]),
  }
}

async function eventually<T>(operation: () => Promise<T>, predicate: (value: T) => boolean): Promise<T> {
  const deadline = Date.now() + 5_000
  while (Date.now() < deadline) {
    const value = await operation()
    if (predicate(value)) return value
    await new Promise((resolve) => setTimeout(resolve, 25))
  }
  throw new Error('Condition was not reached')
}

const postgres = new PGlite()
const database = new PGlitePoolAdapter(postgres) as unknown as Database
let storageRoot: string
let api: Awaited<ReturnType<typeof buildApi>>
let processor: InvoiceProcessor
let processedJobId: string
let processedBatchId: string

beforeAll(async () => {
  storageRoot = await mkdtemp(resolve(tmpdir(), 'ies-node-test-'))
  const migrations = resolve('db/migrations')
  for (const file of (await readdir(migrations)).filter((name) => /^\d+_.+\.sql$/.test(name)).sort()) {
    await postgres.exec(await readFile(resolve(migrations, file), 'utf8'))
  }
  const config = loadConfig({
    NODE_ENV: 'test',
    IES_STORAGE_ROOT: storageRoot,
    IES_PROCESSOR_POLL_MS: '100',
    IES_PROCESSOR_CONCURRENCY: '1',
    IES_AUTH_ENABLED: 'false',
  })
  api = await buildApi(config, database)
  processor = new InvoiceProcessor(config, database, async (_configuration, input) => ({
    document_id: input.jobId,
    invoice: {
      header: {
        invoiceNumber: { value: 'TEST-100', confidence: 0.99, source: 'test' },
        invoiceDate: { value: new Date().toISOString().slice(0, 10), confidence: 0.99, source: 'test' },
        currency: { value: 'USD', confidence: 0.99, source: 'test' },
      },
      vendor: { name: { value: 'Synthetic Vendor', confidence: 0.99, source: 'test' } },
      amounts: {
        tax: { value: 9, confidence: 0.99, source: 'test' },
        total: { value: 109, confidence: 0.99, source: 'test' },
      },
      lineItems: [{
        lineNumber: { value: '1', confidence: 0.99, source: 'test' },
        description: { value: 'Service', confidence: 0.99, source: 'test' },
        amount: { value: 100, confidence: 0.99, source: 'test' },
      }],
    },
    overall_confidence: 0.99,
    engine: 'paddleocr+qwen-test',
    ocr_pages: 1,
    processing_ms: 50,
    warnings: [],
  }))
  processor.start()
}, 30_000)

afterAll(async () => {
  await processor.stop()
  await api.close()
  await database.end()
  await rm(storageRoot, { recursive: true, force: true })
}, 30_000)

describe('Node microservice pipeline', () => {
  it('processes an upload through the durable task and normalized extraction tables', async () => {
    const upload = multipart('invoice.pdf', Buffer.from('%PDF-1.4\n%%EOF\n'))
    const response = await api.inject({
      method: 'POST',
      url: '/api/v1/invoices',
      headers: { 'content-type': upload.contentType },
      payload: upload.body,
    })
    expect(response.statusCode).toBe(202)
    const payload = response.json()
    const jobId = payload.jobs[0].id as string
    processedJobId = jobId
    processedBatchId = payload.batchId as string

    const job = await eventually(
      async () => (await api.inject({ method: 'GET', url: `/api/v1/invoices/${jobId}` })).json(),
      (value) => value.status === 'COMPLETED',
    )
    expect(job.engine).toBe('paddleocr+qwen-test')
    expect(job.confidence).toBe(0.99)

    const source = await api.inject({ method: 'GET', url: `/api/v1/invoices/${jobId}/source` })
    expect(source.statusCode).toBe(200)
    expect(source.headers['content-type']).toContain('application/pdf')
    expect(source.headers['content-disposition']).toContain('invoice.pdf')
    expect(source.headers['x-frame-options']).toBe('SAMEORIGIN')
    expect(source.rawPayload).toEqual(Buffer.from('%PDF-1.4\n%%EOF\n'))

    const fields = await postgres.query<{ field_path: string }>(
      'SELECT field_path FROM extracted_fields ORDER BY field_path',
    )
    expect(fields.rows.map((row) => row.field_path)).toContain('header.invoiceNumber')
    const lines = await postgres.query<{ count: number }>('SELECT count(*)::integer AS count FROM invoice_line_items')
    expect(lines.rows[0]?.count).toBe(1)
    const sopHeader = await postgres.query<{ invoice_number: string; processing_state: string }>(
      'SELECT invoice_number, processing_state FROM invoice_headers WHERE invoice_id = $1',
      [jobId],
    )
    expect(sopHeader.rows[0]).toMatchObject({ invoice_number: 'TEST-100', processing_state: 'Approved' })
    const sopFields = await postgres.query<{ field_name: string }>(
      'SELECT field_name FROM field_extraction_details ORDER BY field_name',
    )
    expect(sopFields.rows.map((row) => row.field_name)).toContain('header.invoiceNumber')
    const sopLines = await postgres.query<{ count: number }>('SELECT count(*)::integer AS count FROM line_items')
    expect(sopLines.rows[0]?.count).toBe(1)
    const sopFiles = await postgres.query<{ count: number }>('SELECT count(*)::integer AS count FROM file_details')
    expect(sopFiles.rows[0]?.count).toBe(1)
    const sopAudit = await postgres.query<{ count: number }>('SELECT count(*)::integer AS count FROM audit_trails')
    expect(Number(sopAudit.rows[0]?.count)).toBeGreaterThan(0)
    const tasks = await postgres.query<{ state: string }>('SELECT state FROM processing_tasks')
    expect(tasks.rows[0]?.state).toBe('COMPLETED')
  })

  it('downloads a review-ready audit package for one invoice', async () => {
    const response = await api.inject({ method: 'GET', url: `/api/v1/invoices/${processedJobId}/audit` })
    expect(response.statusCode).toBe(200)
    expect(response.headers['content-type']).toContain('application/zip')
    expect(response.headers['content-disposition']).toContain('-audit.zip')
    expect(response.headers['cache-control']).toBe('private, no-store')
    expect(response.rawPayload.subarray(0, 4)).toEqual(Buffer.from([0x50, 0x4b, 0x03, 0x04]))
    const archive = response.rawPayload.toString('utf8')
    expect(archive).toContain('source/invoice.pdf')
    expect(archive).toContain('extracted-fields.json')
    expect(archive).toContain('extracted-fields.csv')
    expect(archive).toContain('review-template.json')
    expect(archive).toContain('TEST-100')
    expect(archive).toContain('%PDF-1.4')
    expect(archive).toContain('AUDIT_PACKAGE_REQUESTED')
  })

  it('downloads a batch audit package with an invoice folder', async () => {
    const response = await api.inject({ method: 'GET', url: `/api/v1/batches/${processedBatchId}/audit` })
    expect(response.statusCode).toBe(200)
    expect(response.headers['content-type']).toContain('application/zip')
    expect(response.headers['content-disposition']).toContain(`batch-${processedBatchId}-audit.zip`)
    const archive = response.rawPayload.toString('utf8')
    expect(archive).toContain(`invoices/001-${processedJobId}/source/invoice.pdf`)
    expect(archive).toContain('batch-audit-events.json')
    expect(archive).toContain('BATCH_AUDIT_PACKAGE_REQUESTED')
  })
})
