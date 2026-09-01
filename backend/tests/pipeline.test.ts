import { mkdtemp, readFile, rm } from 'node:fs/promises'
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
      Buffer.from(`--${boundary}\r\nContent-Disposition: form-data; name="files"; filename="${filename}"\r\nContent-Type: application/pdf\r\n\r\n`),
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

beforeAll(async () => {
  storageRoot = await mkdtemp(resolve(tmpdir(), 'ies-node-test-'))
  await postgres.exec(await readFile(resolve('db/migrations/001_node_microservices.sql'), 'utf8'))
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
    const jobId = response.json().jobs[0].id as string

    const job = await eventually(
      async () => (await api.inject({ method: 'GET', url: `/api/v1/invoices/${jobId}` })).json(),
      (value) => value.status === 'COMPLETED',
    )
    expect(job.engine).toBe('paddleocr+qwen-test')
    expect(job.confidence).toBe(0.99)

    const fields = await postgres.query<{ field_path: string }>(
      'SELECT field_path FROM extracted_fields ORDER BY field_path',
    )
    expect(fields.rows.map((row) => row.field_path)).toContain('header.invoiceNumber')
    const lines = await postgres.query<{ count: number }>('SELECT count(*)::integer AS count FROM invoice_line_items')
    expect(lines.rows[0]?.count).toBe(1)
    const tasks = await postgres.query<{ state: string }>('SELECT state FROM processing_tasks')
    expect(tasks.rows[0]?.state).toBe('COMPLETED')
  })
})
