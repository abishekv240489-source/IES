import { readFile } from 'node:fs/promises'
import { resolve } from 'node:path'

import { PGlite } from '@electric-sql/pglite'
import { afterAll, beforeAll, describe, expect, it } from 'vitest'

const database = new PGlite()

beforeAll(async () => {
  const sql = await readFile(resolve('db/migrations/001_node_microservices.sql'), 'utf8')
  await database.exec(sql)
})

afterAll(async () => database.close())

describe('PostgreSQL schema', () => {
  it('creates every application table and the release gate view', async () => {
    const tables = await database.query<{ table_name: string }>(
      `SELECT table_name FROM information_schema.tables
       WHERE table_schema = 'public' AND table_type = 'BASE TABLE' ORDER BY table_name`,
    )
    expect(tables.rows.map((row) => row.table_name)).toEqual(expect.arrayContaining([
      'audit_events',
      'benchmark_document_results',
      'benchmark_field_results',
      'benchmark_runs',
      'extracted_fields',
      'extraction_revisions',
      'invoice_batches',
      'invoice_jobs',
      'invoice_line_items',
      'processing_tasks',
      'tenants',
      'validation_issues',
    ]))
    const view = await database.query<{ table_name: string }>(
      "SELECT table_name FROM information_schema.views WHERE table_name = 'release_accuracy_status'",
    )
    expect(view.rows).toHaveLength(1)
  })

  it('enforces job confidence and status constraints', async () => {
    await database.exec(`
      INSERT INTO invoice_batches(id, tenant_id, submitted_by, document_count)
      VALUES ('10000000-0000-4000-8000-000000000001', '00000000-0000-4000-8000-000000000001', 'test', 1)
    `)
    await expect(database.exec(`
      INSERT INTO invoice_jobs(
        id, tenant_id, batch_id, original_filename, stored_filename, sha256,
        content_type, size_bytes, status, overall_confidence
      ) VALUES (
        '20000000-0000-4000-8000-000000000001', '00000000-0000-4000-8000-000000000001',
        '10000000-0000-4000-8000-000000000001', 'invoice.pdf', 'stored.pdf',
        'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa', 'application/pdf', 100, 'QUEUED', 1.1
      )
    `)).rejects.toThrow()
  })

  it('rejects release approval without a representative holdout', async () => {
    await database.exec(`
      INSERT INTO benchmark_runs(
        id, tenant_id, dataset_name, dataset_fingerprint, model_name, model_configuration,
        status, field_accuracy, critical_field_accuracy, line_item_f1, p95_latency_ms,
        invoices_per_hour, representative_holdout, completed_at, created_by
      ) VALUES (
        '30000000-0000-4000-8000-000000000001', '00000000-0000-4000-8000-000000000001',
        'synthetic', 'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb',
        'qwen-test', '{}', 'PASSED', 0.99, 0.99, 0.99, 1000, 1000, false, now(), 'test'
      )
    `)
    const result = await database.query<{ release_approved: boolean }>(
      "SELECT release_approved FROM release_accuracy_status WHERE benchmark_run_id = '30000000-0000-4000-8000-000000000001'",
    )
    expect(result.rows[0]?.release_approved).toBe(false)
  })
})
