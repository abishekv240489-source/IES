import { readFile } from 'node:fs/promises'

import { z } from 'zod'

import type { Config } from '../../config.js'
import type { AiExtractionResponse } from '../../domain/types.js'

const responseSchema = z.object({
  document_id: z.string(),
  invoice: z.record(z.string(), z.unknown()),
  overall_confidence: z.number().min(0).max(1),
  engine: z.string().min(1),
  ocr_pages: z.number().int().nonnegative(),
  processing_ms: z.number().nonnegative(),
  warnings: z.array(z.string()),
})

export async function extractInvoice(
  config: Config,
  input: { jobId: string; path: string; originalFilename: string; contentType: string },
): Promise<AiExtractionResponse> {
  const bytes = await readFile(input.path)
  const body = new FormData()
  body.set('document_id', input.jobId)
  body.set('file', new Blob([bytes], { type: input.contentType }), input.originalFilename)
  const response = await fetch(`${config.IES_AI_WORKER_URL.replace(/\/$/, '')}/v1/extract`, {
    method: 'POST',
    body,
    signal: AbortSignal.timeout(config.IES_AI_TIMEOUT_MS),
  })
  if (!response.ok) throw new Error(`AI_WORKER_REJECTED_${response.status}`)
  return responseSchema.parse(await response.json())
}
