import { mkdtemp, rm, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'

import { afterEach, describe, expect, it, vi } from 'vitest'

import { loadConfig } from '../src/config.js'
import { extractInvoice } from '../src/services/processor/ai-client.js'

afterEach(() => vi.unstubAllGlobals())

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
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('', { status: 503 })))
    await withInput(async (input) => {
      await expect(extractInvoice(loadConfig({}), input)).rejects.toThrow('AI_WORKER_BUSY')
    })
  })

  it('reports pipeline timeouts explicitly', async () => {
    vi.stubGlobal('fetch', vi.fn().mockImplementation((_url, options) => new Promise((_resolve, reject) => {
      options.signal.addEventListener('abort', () => reject(options.signal.reason), { once: true })
    })))
    await withInput(async (input) => {
      await expect(extractInvoice(loadConfig({ IES_AI_TIMEOUT_MS: '1000' }), input)).rejects.toThrow('AI_WORKER_TIMEOUT')
    })
  })
})
